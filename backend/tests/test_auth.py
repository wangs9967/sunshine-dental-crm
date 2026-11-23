import json
import os
import secrets
import socket
import subprocess
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from threading import Barrier
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from redis import Redis
from sqlalchemy import URL, create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

import app.auth.sessions as sessions_module
from app.auth.sessions import KEY_PREFIX, SessionReference, SessionService, TokenPair, digest
from app.db.models import Account, Base, Member, OperationLog, StaffProfile
from app.db.session import get_db
from app.http import install_http_handlers
from app.main import app

AUTH = "/api/v1/auth"


@contextmanager
def container(image: str, port: int, *options: str, env: dict[str, str] | None = None) -> Iterator[int]:
    name = subprocess.check_output(
        ["docker", "run", "--rm", "-d", "-p", f"127.0.0.1::{port}", *options, image],
        env=env, text=True, timeout=120,
    ).strip()
    try:
        binding = subprocess.check_output(
            ["docker", "port", name, f"{port}/tcp"], text=True, timeout=15,
        ).strip()
        yield int(binding.rsplit(":", 1)[1])
    finally:
        subprocess.run(["docker", "stop", name], check=True, capture_output=True, timeout=30)


@pytest.fixture(scope="module")
def auth_infrastructure() -> Iterator[tuple[Engine, int]]:
    if os.environ.get("SUNSHINE_TEST_AUTH") != "1":
        pytest.skip("Set SUNSHINE_TEST_AUTH=1 to start isolated Redis 7 and PostgreSQL 16")
    password = secrets.token_urlsafe(24)
    with (
        container(
            "postgres:16", 5432, "-e", "POSTGRES_PASSWORD",
            env={**os.environ, "POSTGRES_PASSWORD": password},
        ) as pg_port,
        container("redis:7-alpine", 6379) as redis_port,
    ):
        engine = create_engine(URL.create(
            "postgresql+psycopg", username="postgres", password=password, host="127.0.0.1",
            port=pg_port, database="postgres",
        ), connect_args={"connect_timeout": 2}, hide_parameters=True)
        try:
            for attempt in range(60):
                try:
                    with engine.connect() as connection:
                        connection.exec_driver_sql("SELECT 1")
                    break
                except OperationalError:
                    if attempt == 59:
                        raise
                    time.sleep(0.5)
            tables = ("accounts", "members", "staff_profiles", "operation_logs")
            Base.metadata.create_all(engine, tables=[Base.metadata.tables[name] for name in tables])
            yield engine, redis_port
        finally:
            engine.dispose()


@dataclass
class AuthFixture:
    client: TestClient
    service: SessionService
    engine: Engine
    account_id: UUID
    tokens: TokenPair


@pytest.fixture
def auth(auth_infrastructure: tuple[Engine, int], monkeypatch: pytest.MonkeyPatch) -> Iterator[AuthFixture]:
    engine, redis_port = auth_infrastructure
    monkeypatch.setenv("REDIS_HOST", "127.0.0.1")
    monkeypatch.setenv("REDIS_PORT", str(redis_port))
    monkeypatch.setenv("REDIS_DB", "0")
    monkeypatch.setenv("REDIS_PASSWORD", "")
    monkeypatch.setenv("AUTH_ACCESS_TTL_SECONDS", "600")
    monkeypatch.setenv("AUTH_SESSION_TTL_SECONDS", "604800")

    def test_db() -> Iterator[Session]:
        with Session(engine) as db:
            yield db

    account_id = uuid4()
    with Session(engine) as db:
        db.add(Account(id=account_id, username=account_id.hex, wechat_openid=account_id.hex))
        db.flush()
        db.add(StaffProfile(account_id=account_id, display_name="Test account", role="admin"))
        db.commit()

    monkeypatch.setitem(app.dependency_overrides, get_db, test_db)
    with TestClient(app) as client:
        service = app.state.auth_sessions
        tokens = service.issue(account_id, "admin", "admin_web")
        yield AuthFixture(client, service, engine, account_id, tokens)


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def assert_error(response: Response, status: int, code: str) -> None:
    assert response.status_code == status
    body = response.json()
    assert body["success"] is False
    assert body["request_id"] == response.headers["X-Request-ID"]
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == code


def test_access_and_response_contract(auth: AuthFixture) -> None:
    response = auth.client.get(f"{AUTH}/me?role=employee&account_id={uuid4()}", headers={
        **bearer(auth.tokens.access_token), "X-Request-ID": "untrusted-value",
    })
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    request_id = response.headers["X-Request-ID"]
    assert str(UUID(request_id)) == request_id
    assert response.json() == {
        "success": True, "request_id": request_id, "data": {
            "account_id": str(auth.account_id), "selected_role": "admin",
            "available_roles": ["admin"], "registration_required": False,
        },
    }
    for token in ("malformed", secrets.token_urlsafe(32), auth.tokens.refresh_token):
        response = auth.client.get(f"{AUTH}/me", headers=bearer(token))
        assert_error(response, 401, "INVALID_SESSION")
        assert response.headers["WWW-Authenticate"] == "Bearer"
    assert_error(auth.client.get(f"{AUTH}/me"), 401, "INVALID_SESSION")


def test_access_expiry_does_not_prevent_refresh(auth: AuthFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    expires = auth.service.access(auth.tokens.access_token).record.access_expires_at
    monkeypatch.setattr(sessions_module, "time", SimpleNamespace(time=lambda: expires))
    assert_error(auth.client.get(f"{AUTH}/me", headers=bearer(auth.tokens.access_token)), 401, "INVALID_SESSION")
    assert auth.client.post(f"{AUTH}/refresh", json={"refresh_token": auth.tokens.refresh_token}).status_code == 200


def test_absolute_session_expiry_disallows_refresh(auth: AuthFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    expires = auth.service.access(auth.tokens.access_token).record.expires_at
    monkeypatch.setattr(sessions_module, "time", SimpleNamespace(time=lambda: expires))
    assert_error(auth.client.post(f"{AUTH}/refresh", json={"refresh_token": auth.tokens.refresh_token}),
                 401, "INVALID_SESSION")


def test_refresh_rotation_and_replay_revokes_family(auth: AuthFixture) -> None:
    initial = auth.service.access(auth.tokens.access_token)
    response = auth.client.post(f"{AUTH}/refresh", json={"refresh_token": auth.tokens.refresh_token})
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    data = response.json()["data"]
    assert 0 < data["expires_in"] <= 600
    assert data["access_token"] != auth.tokens.access_token
    assert data["refresh_token"] != auth.tokens.refresh_token
    renewed = auth.service.access(data["access_token"])
    assert renewed.key == initial.key
    assert renewed.record.expires_at == initial.record.expires_at
    assert_error(auth.client.get(f"{AUTH}/me", headers=bearer(auth.tokens.access_token)), 401, "INVALID_SESSION")
    assert auth.client.get(f"{AUTH}/me", headers=bearer(data["access_token"])).status_code == 200

    replay = auth.client.post(f"{AUTH}/refresh", json={"refresh_token": auth.tokens.refresh_token})
    assert_error(replay, 401, "INVALID_SESSION")
    assert_error(auth.client.get(f"{AUTH}/me", headers=bearer(data["access_token"])), 401, "INVALID_SESSION")
    assert_error(auth.client.post(f"{AUTH}/refresh", json={"refresh_token": data["refresh_token"]}),
                 401, "INVALID_SESSION")
    with Session(auth.engine) as db:
        assert db.scalar(select(OperationLog.summary).where(
            OperationLog.request_id == replay.headers["X-Request-ID"],
        )) == "refresh_replay"


def test_concurrent_refresh_has_one_winner(auth: AuthFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    barrier = Barrier(2, timeout=10)
    rotate = SessionService.rotate

    def concurrent_rotate(service: SessionService, reference: SessionReference) -> TokenPair:
        barrier.wait()
        return rotate(service, reference)

    def refresh() -> Response:
        return auth.client.post(f"{AUTH}/refresh", json={"refresh_token": auth.tokens.refresh_token})

    monkeypatch.setattr(SessionService, "rotate", concurrent_rotate)
    with ThreadPoolExecutor(max_workers=2) as executor:
        requests = [executor.submit(refresh) for _ in range(2)]
        responses = [request.result(timeout=15) for request in requests]
    assert sorted(response.status_code for response in responses) == [200, 401]
    winner = next(response.json()["data"] for response in responses if response.status_code == 200)
    assert_error(auth.client.get(f"{AUTH}/me", headers=bearer(winner["access_token"])), 401, "INVALID_SESSION")


def test_logout_revokes_access_and_refresh(auth: AuthFixture) -> None:
    response = auth.client.post(f"{AUTH}/logout", headers=bearer(auth.tokens.access_token))
    assert response.json()["data"] == {"logged_out": True}
    assert_error(auth.client.get(f"{AUTH}/me", headers=bearer(auth.tokens.access_token)), 401, "INVALID_SESSION")
    assert_error(auth.client.post(f"{AUTH}/refresh", json={"refresh_token": auth.tokens.refresh_token}),
                 401, "INVALID_SESSION")
    assert_error(auth.client.post(f"{AUTH}/logout", headers=bearer(auth.tokens.access_token)),
                 401, "INVALID_SESSION")


@pytest.mark.parametrize("change", ["account_disabled", "staff_disabled", "role_changed"])
def test_identity_is_checked_on_each_request(auth: AuthFixture, change: str) -> None:
    assert auth.client.get(f"{AUTH}/me", headers=bearer(auth.tokens.access_token)).is_success
    with Session(auth.engine) as db:
        if change == "account_disabled":
            account = db.get_one(Account, auth.account_id)
            account.status = "disabled"
        else:
            staff = db.scalars(select(StaffProfile).where(StaffProfile.account_id == auth.account_id)).one()
            if change == "staff_disabled":
                staff.status = "disabled"
            else:
                staff.role = "manager"
        db.commit()
    assert_error(auth.client.get(f"{AUTH}/me", headers=bearer(auth.tokens.access_token)), 401, "INVALID_SESSION")
    assert_error(auth.client.post(f"{AUTH}/refresh", json={"refresh_token": auth.tokens.refresh_token}),
                 401, "INVALID_SESSION")


def test_channel_and_registration_identity(auth: AuthFixture) -> None:
    signup = auth.service.issue(auth.account_id, None, "miniprogram")
    response = auth.client.get(f"{AUTH}/me", headers=bearer(signup.access_token))
    assert response.json()["data"] == {
        "account_id": str(auth.account_id), "selected_role": None,
        "available_roles": [], "registration_required": True,
    }
    wrong_channel = auth.service.issue(auth.account_id, "admin", "miniprogram")
    assert_error(auth.client.get(f"{AUTH}/me", headers=bearer(wrong_channel.access_token)), 401, "INVALID_SESSION")

    with Session(auth.engine) as db:
        db.add(Member(
            account_id=auth.account_id, member_no=auth.account_id.hex, name="Test member",
            birthday=date(2000, 1, 1), phone_ciphertext=b"ciphertext", phone_search_hash=b"digest",
            register_source="direct",
        ))
        db.commit()
    assert_error(auth.client.get(f"{AUTH}/me", headers=bearer(signup.access_token)), 401, "INVALID_SESSION")
    member = auth.service.issue(auth.account_id, "member", "miniprogram")
    assert auth.client.get(f"{AUTH}/me", headers=bearer(member.access_token)).json()["data"]["available_roles"] == [
        "member",
    ]


def test_redis_outage_fails_closed(auth: AuthFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    # Reserve a loopback port without listening so the real Redis client cannot connect.
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        with Redis(host="127.0.0.1", port=reserved.getsockname()[1], socket_connect_timeout=0.2) as cache:
            monkeypatch.setattr(auth.service, "cache", cache)
            headers = bearer(auth.tokens.access_token)
            assert_error(auth.client.get(f"{AUTH}/me", headers=headers), 503, "AUTH_UNAVAILABLE")
            assert_error(auth.client.post(f"{AUTH}/logout", headers=headers), 503, "AUTH_UNAVAILABLE")
            assert_error(auth.client.post(f"{AUTH}/refresh", json={"refresh_token": auth.tokens.refresh_token}),
                         503, "AUTH_UNAVAILABLE")
            assert auth.client.get("/health").is_success


def test_audit_and_redis_exclude_credentials(auth: AuthFixture) -> None:
    pair = auth.tokens
    reference = auth.service.access(pair.access_token)
    raw = auth.service.cache.get(reference.key)
    assert isinstance(raw, str)
    assert pair.access_token not in raw and pair.refresh_token not in raw
    assert json.loads(raw)["refresh_digest"] == digest(pair.refresh_token)
    for kind, token in (("access", pair.access_token), ("refresh", pair.refresh_token)):
        assert auth.service.cache.get(f"{KEY_PREFIX}:{kind}:{digest(token)}") == reference.key

    unexpected = "untrusted-credential-value"
    invalid = auth.client.post(f"{AUTH}/refresh", json={
        "refresh_token": {"password": unexpected}, unexpected: pair.refresh_token,
    })
    assert_error(invalid, 422, "VALIDATION_ERROR")
    assert unexpected not in invalid.text and pair.refresh_token not in invalid.text
    malformed = auth.client.post(
        f"{AUTH}/refresh", content="{",
        headers={"Content-Type": "application/json"},
    )
    assert_error(malformed, 400, "INVALID_REQUEST")
    refresh = auth.client.post(f"{AUTH}/refresh", json={"refresh_token": pair.refresh_token})
    assert refresh.is_success
    new_pair = refresh.json()["data"]
    logout = auth.client.post(f"{AUTH}/logout", headers=bearer(new_pair["access_token"]))
    assert logout.is_success

    with Session(auth.engine) as db:
        rows = db.scalars(select(OperationLog).where(OperationLog.request_id.in_([
            refresh.headers["X-Request-ID"], logout.headers["X-Request-ID"],
        ]))).all()
        assert {row.action for row in rows} == {"refresh", "logout"}
        for row in rows:
            assert row.actor_account_id == auth.account_id and row.actor_role == "admin"
            assert row.summary == "success" and row.module == "auth"
            assert row.before_data is None and row.after_data is None


def test_unexpected_error_uses_request_id_without_exception_details(caplog: pytest.LogCaptureFixture) -> None:
    test_app = FastAPI()
    install_http_handlers(test_app)

    @test_app.get("/broken")
    def broken() -> None:
        raise RuntimeError("secret test value")

    with TestClient(test_app) as client:
        response = client.get("/broken")
        assert_error(response, 500, "INTERNAL_ERROR")
        assert response.headers["X-Request-ID"] in caplog.text
        assert "secret test value" not in response.text + caplog.text
        assert_error(client.get("/missing"), 404, "NOT_FOUND")
