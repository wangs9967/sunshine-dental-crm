import hashlib
import json
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import Response
from pydantic import SecretStr
from sqlalchemy import event, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.sessions import SessionService
from app.db.models import Account, CustomerAssignment, CustomerStatus, EmployeeQrToken, Member, PointsAccount, StaffProfile
from app.http import APIError
from app.main import app
from test_auth import AUTH, AuthFixture, assert_error, auth, auth_infrastructure, bearer

FORM = {"name": "测试会员", "birthday": "2000-01-01", "phone": "19900000000"}
REGISTER = "/api/v1/members/register"
POINTS = "/api/v1/members/me/points"
PROFILE = "/api/v1/members/me"


@pytest.fixture
def wechat(auth: AuthFixture, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    settings = app.state.auth_settings
    settings.wechat_app_id = "test-app"
    settings.wechat_app_secret = SecretStr(secrets.token_urlsafe(24))
    settings.phone_encryption_key = SecretStr(secrets.token_urlsafe(32) + "=")
    settings.phone_lookup_hmac_key = SecretStr(secrets.token_urlsafe(32) + "=")
    payload: dict[str, object] = {"openid": f"test-{uuid4().hex}", "session_key": "fixture-only"}

    class FakeConnection:
        status = 200

        def __init__(self, host: str, timeout: int) -> None:
            assert host == "api.weixin.qq.com" and timeout == 5

        def request(self, method: str, path: str) -> None:
            assert method == "GET" and path.startswith("/sns/jscode2session?")
            assert "appid=test-app" in path and "js_code=temporary-test-code" in path
            if payload.get("timeout"):
                raise TimeoutError("fixture-only")

        def getresponse(self) -> "FakeConnection":
            return self

        def read(self, _: int) -> bytes:
            return json.dumps(payload).encode()

        def close(self) -> None:
            pass

    monkeypatch.setattr("app.auth.wechat.HTTPSConnection", FakeConnection)
    return payload


def login(auth: AuthFixture, scene: str | None = None) -> dict:
    response = auth.client.post(f"{AUTH}/wechat/login", json={"code": "temporary-test-code", "scene_token": scene})
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert "fixture-only" not in response.text and "openid" not in response.text
    return response.json()["data"]


def register(auth: AuthFixture, session: dict, scene: str | None = None) -> Response:
    return auth.client.post(REGISTER, headers=bearer(session["access_token"]), json={**FORM, "scene_token": scene})


def source_code(auth: AuthFixture, *, expired: bool = False) -> tuple[str, UUID]:
    token = secrets.token_urlsafe(24)
    with Session(auth.engine) as db:
        staff_id = db.scalars(select(StaffProfile.id).where(StaffProfile.account_id == auth.account_id)).one()
        db.add(EmployeeQrToken(
            staff_id=staff_id, token_hash=hashlib.sha256(token.encode()).digest(),
            expires_at=datetime.now(UTC) + timedelta(minutes=-1 if expired else 10),
        ))
        db.commit()
    return token, staff_id


def test_register_then_login_and_logout(auth: AuthFixture, wechat: dict[str, object]) -> None:
    session = login(auth)
    assert session["registration_required"] and session["selected_role"] is None
    assert_error(auth.client.get(POINTS, headers=bearer(session["access_token"])), 403, "FORBIDDEN")
    response = register(auth, session)
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["source_status"] == "none" and data["phone_masked"] == "199****0000"
    assert FORM["phone"] not in response.text
    assert "phone_search_hash" not in response.text and "phone_ciphertext" not in response.text
    member_session = data["session"]
    assert member_session["selected_role"] == "member" and not member_session["registration_required"]
    assert_error(auth.client.get(f"{AUTH}/me", headers=bearer(session["access_token"])), 401, "INVALID_SESSION")
    assert_error(register(auth, session), 409, "MEMBER_ALREADY_REGISTERED")
    headers = bearer(member_session["access_token"])
    assert auth.client.get(POINTS, headers=headers).json()["data"] == {
        "member_id": data["id"], "balance": "0", "total_earned": "0", "total_spent": "0",
    }
    with Session(auth.engine) as db:
        status = db.scalars(select(CustomerStatus).where(CustomerStatus.member_id == UUID(data["id"]))).one()
        assert (status.visit_status, status.consume_status, status.deal_status) == ("not_visited", "not_consumed", "not_dealt")
    assert auth.client.post(f"{AUTH}/logout", headers=headers).is_success
    assert_error(auth.client.get(POINTS, headers=headers), 401, "INVALID_SESSION")
    again = login(auth)
    assert not again["registration_required"] and again["account_id"] == session["account_id"]


def test_shared_phone_keeps_separate_members_and_random_ciphertexts(auth: AuthFixture, wechat: dict[str, object]) -> None:
    first = register(auth, login(auth)).json()["data"]
    wechat["openid"] = f"test-{uuid4().hex}"
    second = register(auth, login(auth)).json()["data"]
    assert first["id"] != second["id"] and first["member_no"] != second["member_no"]
    with Session(auth.engine) as db:
        records = [db.get_one(Member, UUID(row["id"])) for row in (first, second)]
        assert records[0].phone_search_hash == records[1].phone_search_hash
        assert records[0].phone_ciphertext != records[1].phone_ciphertext
        for record in records:
            assert FORM["phone"].encode() not in record.phone_ciphertext
    for result in (first, second):
        own_points = auth.client.get(POINTS, headers=bearer(result["session"]["access_token"])).json()["data"]
        assert own_points["member_id"] == result["id"]


def test_source_binding_is_permanent_for_existing_member(auth: AuthFixture, wechat: dict[str, object]) -> None:
    token, staff_id = source_code(auth)
    data = register(auth, login(auth, token), token).json()["data"]
    assert data["source_status"] == "bound"
    new_staff_id = uuid4()
    different_token = secrets.token_urlsafe(24)
    with Session(auth.engine) as db:
        account = Account()
        db.add(account)
        db.flush()
        db.add(StaffProfile(id=new_staff_id, account_id=account.id, role="employee", display_name="测试员工乙"))
        db.flush()
        db.add(EmployeeQrToken(
            staff_id=new_staff_id, token_hash=hashlib.sha256(different_token.encode()).digest(),
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        ))
        db.commit()
    existing = login(auth, different_token)
    assert not existing["registration_required"]
    assert_error(register(auth, existing, different_token), 409, "MEMBER_ALREADY_REGISTERED")
    with Session(auth.engine) as db:
        member = db.get_one(Member, UUID(data["id"]))
        assignment = db.scalars(select(CustomerAssignment).where(CustomerAssignment.member_id == member.id)).one()
        assert member.source_employee_id == staff_id and member.register_source == "employee_qr"
        assert assignment.staff_id == staff_id and assignment.is_current


@pytest.mark.parametrize("expired", [False, True])
def test_invalid_source_allows_registration(auth: AuthFixture, wechat: dict[str, object], expired: bool) -> None:
    token = source_code(auth, expired=True)[0] if expired else "unrecognized"
    response = register(auth, login(auth, token), token)
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["source_status"] == "invalid"
    with Session(auth.engine) as db:
        member = db.get_one(Member, UUID(data["id"]))
        assert member.source_employee_id is None and member.register_source == "direct"
        assert db.scalar(select(CustomerAssignment.id).where(CustomerAssignment.member_id == member.id)) is None


@pytest.mark.parametrize(("fields", "status", "code"), [
    ({"errcode": 40029, "errmsg": "fixture-only"}, 400, "WECHAT_CODE_INVALID"),
    ({"errcode": 40163}, 400, "WECHAT_CODE_INVALID"),
    ({"timeout": True}, 502, "WECHAT_UNAVAILABLE"),
    ({"errcode": 40013, "errmsg": "fixture-only"}, 502, "WECHAT_UNAVAILABLE"),
])
def test_wechat_errors_are_redacted(
    auth: AuthFixture, wechat: dict[str, object], fields: dict[str, object], status: int, code: str,
) -> None:
    wechat.update(fields)
    response = auth.client.post(f"{AUTH}/wechat/login", json={"code": "temporary-test-code"})
    assert_error(response, status, code)
    assert "fixture-only" not in response.text and "temporary-test-code" not in response.text
    fake_openid = auth.client.post(f"{AUTH}/wechat/login", json={"code": "temporary-test-code", "openid": "spoof"})
    assert_error(fake_openid, 422, "VALIDATION_ERROR")


@pytest.mark.parametrize("failure", ["db_write", "session_issue"])
def test_registration_rolls_back_and_can_retry(
    auth: AuthFixture, wechat: dict[str, object], monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    session = login(auth)

    def db_failure(*_: object) -> None:
        raise SQLAlchemyError("fixture-only")

    def redis_failure(*_: object) -> None:
        raise APIError(503, "AUTH_UNAVAILABLE", "认证服务暂时不可用")

    if failure == "db_write":
        event.listen(PointsAccount, "before_insert", db_failure)
    try:
        with monkeypatch.context() as scoped:
            if failure == "session_issue":
                scoped.setattr(SessionService, "issue", redis_failure)
            response = register(auth, session, source_code(auth)[0])
            code = "MEMBER_REGISTRATION_UNAVAILABLE" if failure == "db_write" else "AUTH_UNAVAILABLE"
            assert_error(response, 503, code)
            assert "fixture-only" not in response.text
    finally:
        if failure == "db_write":
            event.remove(PointsAccount, "before_insert", db_failure)
    with Session(auth.engine) as db:
        assert db.scalar(select(Member.id).where(Member.account_id == UUID(session["account_id"]))) is None
    assert register(auth, session).status_code == 201


def test_concurrent_registration_creates_one_member(auth: AuthFixture, wechat: dict[str, object]) -> None:
    session = login(auth)
    with ThreadPoolExecutor(max_workers=2) as pool:
        requests = [pool.submit(register, auth, session) for _ in range(2)]
        assert sorted(request.result(timeout=10).status_code for request in requests) == [201, 409]


def test_member_profile_returns_only_own_masked_details(auth: AuthFixture, wechat: dict[str, object]) -> None:
    signup = login(auth)
    first = register(auth, signup).json()["data"]
    wechat["openid"] = f"test-{uuid4().hex}"
    other_signup = login(auth)
    other = register(auth, other_signup).json()["data"]

    response = auth.client.get(
        PROFILE, params={"account_id": other_signup["account_id"], "member_id": other["id"]},
        headers=bearer(first["session"]["access_token"]),
    )
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["data"] == {
        "id": first["id"], "member_no": first["member_no"], "name": FORM["name"], "birthday": FORM["birthday"],
        "phone_masked": "199****0000", "status": "active", "registered_at": first["registered_at"],
    }
    assert FORM["phone"] not in response.text and other["id"] not in response.text
    other_response = auth.client.get(PROFILE, headers=bearer(other["session"]["access_token"]))
    assert other_response.json()["data"]["id"] == other["id"]
    assert_error(auth.client.patch(PROFILE, headers=bearer(first["session"]["access_token"])),
                 405, "METHOD_NOT_ALLOWED")


def test_member_profile_rejects_other_sessions(auth: AuthFixture, wechat: dict[str, object]) -> None:
    assert_error(auth.client.get(PROFILE), 401, "INVALID_SESSION")
    assert_error(auth.client.get(PROFILE, headers=bearer(auth.tokens.access_token)), 403, "FORBIDDEN")
    signup = login(auth)
    assert_error(auth.client.get(PROFILE, headers=bearer(signup["access_token"])), 403, "FORBIDDEN")
    session = register(auth, signup).json()["data"]["session"]
    headers = bearer(session["access_token"])
    assert auth.client.post(f"{AUTH}/logout", headers=headers).is_success
    assert_error(auth.client.get(PROFILE, headers=headers), 401, "INVALID_SESSION")


def test_member_profile_masks_or_fails_closed_on_unreadable_phone(auth: AuthFixture, wechat: dict[str, object]) -> None:
    member = register(auth, login(auth)).json()["data"]
    with Session(auth.engine) as db:
        db.get_one(Member, UUID(member["id"])).phone_ciphertext = b"\x01" + b"tampered"
        db.commit()
    response = auth.client.get(PROFILE, headers=bearer(member["session"]["access_token"]))
    assert_error(response, 503, "PHONE_PROTECTION_UNAVAILABLE")
    assert "tampered" not in response.text
