import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from httpx import Response
from redis.exceptions import ConnectionError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import routes
from app.auth.sessions import KEY_PREFIX, RejectedSession
from app.config import AuthSettings
from app.db.models import Account, ExchangeOrder, Member, OperationLog, PointsAccount, Product, StaffProfile
from test_auth import AuthFixture, assert_error, auth, auth_infrastructure, bearer
from test_permissions import add_employee, add_member, phones

API = "/api/v1"
STAFF = f"{API}/admin/staff"
BIND = f"{API}/auth/wechat/staff-bind"
LOGIN = f"{API}/auth/wechat/login"
REFRESH = f"{API}/auth/refresh"


def admin(auth: AuthFixture) -> dict[str, str]:
    return bearer(auth.tokens.access_token)


def open_staff(auth: AuthFixture) -> str:
    response = auth.client.post(STAFF, headers=admin(auth), json={"employee_no": uuid4().hex, "display_name": "验收员工"})
    assert response.status_code == 201
    return str(response.json()["data"]["id"])


def invitation(auth: AuthFixture, staff_id: str) -> str:
    response = auth.client.post(f"{STAFF}/{staff_id}/wechat-invitation", headers=admin(auth))
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    return str(response.json()["data"]["qr_payload"])


def use_invite(auth: AuthFixture, qr: str, code: str) -> Response:
    return auth.client.post(BIND, json={"invitation": qr, "code": code})


@pytest.fixture
def wechat_codes(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    codes: dict[str, str] = {}

    def exchange(code: str, settings: AuthSettings) -> str:
        return codes[code]

    monkeypatch.setattr(routes, "exchange_code", exchange)
    return codes


def test_open_staff_permissions_and_duplicates(auth: AuthFixture) -> None:
    body = {"employee_no": uuid4().hex, "display_name": "普通员工"}
    with Session(auth.engine) as db:
        manager_account, manager_staff = add_employee(db, "manager")
        count = db.scalar(select(func.count()).select_from(Account))
        db.commit()
    manager = bearer(auth.service.issue(manager_account, "manager", "admin_web").access_token)
    assert_error(auth.client.post(STAFF, headers=manager, json=body), 403, "FEATURE_NOT_AVAILABLE")
    assert_error(auth.client.post(STAFF, headers=admin(auth), json={**body, "role": "admin"}), 422, "VALIDATION_ERROR")
    created = auth.client.post(STAFF, headers=admin(auth), json=body)
    assert created.status_code == 201
    staff_id = created.json()["data"]["id"]
    expected = {**body, "id": staff_id, "role": "employee", "status": "active", "wechat_bound": False}
    assert created.json()["data"] == expected
    assert auth.client.get(f"{STAFF}/{staff_id}", headers=manager).json()["data"] == expected
    assert_error(auth.client.post(STAFF, headers=admin(auth), json=body), 409, "EMPLOYEE_NO_EXISTS")
    assert_error(auth.client.post(f"{STAFF}/{staff_id}/wechat-invitation", headers=manager), 403, "FEATURE_NOT_AVAILABLE")
    assert_error(auth.client.patch(f"{STAFF}/{staff_id}", headers=manager, json={"status": "disabled"}),
                 403, "FEATURE_NOT_AVAILABLE")
    assert_error(auth.client.patch(f"{STAFF}/{manager_staff}", headers=admin(auth), json={"status": "disabled"}),
                 403, "FORBIDDEN")
    with Session(auth.engine) as db:
        if count is not None:
            assert db.scalar(select(func.count()).select_from(Account)) == count + 1
        account = db.get_one(Account, db.get_one(StaffProfile, UUID(staff_id)).account_id)
        assert account.status == "active" and account.username is None
        assert account.wechat_openid is None and account.password_hash is None


def test_invitation_expiry_reissue_replay_and_conflict(auth: AuthFixture, wechat_codes: dict[str, str]) -> None:
    staff_id = open_staff(auth)
    another = open_staff(auth)
    code, openid = uuid4().hex, uuid4().hex
    wechat_codes[code] = openid
    assert_error(auth.client.post(LOGIN, json={"code": code, "role": "employee"}), 403, "EMPLOYEE_ACCOUNT_UNAVAILABLE")
    first = invitation(auth, staff_id)
    assert openid not in first
    renewed = invitation(auth, staff_id)
    assert renewed != first
    key = f"{KEY_PREFIX}:staff-binding:{staff_id}"
    assert auth.service.cache.get(key) == hashlib.sha256(renewed.encode()).hexdigest()
    ttl = auth.service.cache.ttl(key)
    assert isinstance(ttl, int) and 0 < ttl <= 600
    assert_error(use_invite(auth, first, code), 409, "STAFF_INVITATION_INVALID")
    assert auth.service.cache.expireat(key, 1)
    assert_error(use_invite(auth, renewed, code), 409, "STAFF_INVITATION_INVALID")
    live = invitation(auth, staff_id)
    bound = use_invite(auth, live, code)
    assert bound.status_code == 200 and bound.json()["data"] == {"wechat_bound": True}
    assert_error(use_invite(auth, live, code), 409, "STAFF_INVITATION_INVALID")
    assert_error(auth.client.post(f"{STAFF}/{staff_id}/wechat-invitation", headers=admin(auth)),
                 409, "STAFF_INVITATION_NOT_AVAILABLE")
    other_code = invitation(auth, another)
    assert_error(use_invite(auth, other_code, code), 409, "STAFF_BINDING_CONFLICT")
    assert auth.client.get(f"{STAFF}/{another}", headers=admin(auth)).json()["data"]["wechat_bound"] is False
    with Session(auth.engine) as db:
        logs = db.scalars(select(OperationLog).where(OperationLog.target_id == UUID(staff_id))).all()
        assert {log.action for log in logs} == {"staff_create", "staff_invite", "staff_bind"}
        log = next(log for log in logs if log.action == "staff_bind")
        assert log.request_id == bound.headers["X-Request-ID"] and log.actor_role == "employee"
        serialized = json.dumps([log.after_data for log in logs])
        assert all(value not in serialized for value in (openid, first, renewed, live, code))


def test_concurrent_bind_only_consumes_one_invitation(auth: AuthFixture, wechat_codes: dict[str, str]) -> None:
    staff_id = open_staff(auth)
    qr = invitation(auth, staff_id)
    codes = [uuid4().hex for _ in range(2)]
    for code in codes:
        wechat_codes[code] = uuid4().hex
    barrier = Barrier(2, timeout=10)

    def try_bind(code: str) -> Response:
        barrier.wait()
        return use_invite(auth, qr, code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(try_bind, codes))
    assert sorted(response.status_code for response in responses) == [200, 409]
    assert_error(next(response for response in responses if response.status_code == 409), 409, "STAFF_INVITATION_INVALID")
    with Session(auth.engine) as db:
        logs = db.scalars(select(OperationLog).where(
            OperationLog.target_id == UUID(staff_id), OperationLog.action == "staff_bind",
        )).all()
        assert len(logs) == 1


def test_member_binding_preserves_data_and_staff_lifecycle(
    auth: AuthFixture, phones: None, wechat_codes: dict[str, str],
) -> None:
    with Session(auth.engine) as db:
        member_id = add_member(db)
        account_id = db.get_one(Member, member_id).account_id
        openid = db.get_one(Account, account_id).wechat_openid
        assert openid
        code = uuid4().hex
        wechat_codes[code] = openid
        product = Product(name="验收商品", points_price=1)
        db.add(product)
        db.flush()
        order = ExchangeOrder(
            member_id=member_id, product_id=product.id, quantity=1, points_cost_total=1,
            product_snapshot={"name": product.name}, order_no=uuid4().hex,
            idempotency_key=uuid4().hex, request_fingerprint=bytes(32), created_at=datetime.now(UTC),
        )
        db.add_all([order, PointsAccount(member_id=member_id, balance=100, total_earned=100)])
        db.flush()
        order_id = order.id
        db.commit()
    member_session = auth.client.post(LOGIN, json={"code": code}).json()["data"]
    member_headers = bearer(member_session["access_token"])
    staff_id = open_staff(auth)
    assert use_invite(auth, invitation(auth, staff_id), code).is_success
    employee_request = {"code": code, "role": "employee"}
    employees = [auth.client.post(LOGIN, json=employee_request).json()["data"] for _ in range(2)]
    employee_headers = bearer(employees[0]["access_token"])
    assert employees[0]["account_id"] == member_session["account_id"] == str(account_id)
    assert employees[0]["available_roles"] == ["employee"]
    assert auth.client.get(f"{API}/staff/me", headers=employee_headers).json()["data"]["id"] == staff_id
    assert auth.client.get(f"{API}/staff/me/customers", headers=employee_headers).is_success
    assert_error(auth.client.get(f"{API}/staff/me", headers=member_headers), 403, "FORBIDDEN")

    status_url = f"{STAFF}/{staff_id}"
    disabled = auth.client.patch(status_url, headers=admin(auth), json={"status": "disabled"})
    assert disabled.is_success and disabled.json()["data"]["status"] == "disabled"
    assert_error(auth.client.post(LOGIN, json=employee_request), 403, "EMPLOYEE_ACCOUNT_UNAVAILABLE")
    for employee in employees:
        with pytest.raises(RejectedSession):
            auth.service.access(employee["access_token"])
        with pytest.raises(RejectedSession):
            auth.service.refresh(employee["refresh_token"])
        assert_error(auth.client.get(f"{API}/staff/me/customers", headers=bearer(employee["access_token"])),
                     401, "INVALID_SESSION")
        assert_error(auth.client.post(REFRESH, json={"refresh_token": employee["refresh_token"]}), 401, "INVALID_SESSION")
    assert auth.client.get(f"{API}/members/me", headers=member_headers).json()["data"]["id"] == str(member_id)
    assert auth.client.get(f"{API}/members/me/points", headers=member_headers).json()["data"]["balance"] == "100"
    assert auth.client.get(f"{API}/exchange-orders/{order_id}", headers=member_headers).is_success
    member_refresh = auth.client.post(REFRESH, json={"refresh_token": member_session["refresh_token"]})
    assert member_refresh.json()["data"]["selected_role"] == "member"

    enabled = auth.client.patch(status_url, headers=admin(auth), json={"status": "active"})
    assert enabled.is_success and enabled.json()["data"]["status"] == "active"
    assert_error(auth.client.get(f"{API}/staff/me", headers=employee_headers), 401, "INVALID_SESSION")
    assert_error(auth.client.post(REFRESH, json={"refresh_token": employees[0]["refresh_token"]}), 401, "INVALID_SESSION")
    latest = auth.client.post(LOGIN, json=employee_request).json()["data"]
    assert auth.client.get(f"{API}/staff/me", headers=bearer(latest["access_token"])).is_success
    with Session(auth.engine) as db:
        logs = db.scalars(select(OperationLog).where(
            OperationLog.target_id == UUID(staff_id), OperationLog.action.in_(["staff_disable", "staff_enable"]),
        )).all()
        assert {(log.action, log.request_id) for log in logs} == {
            ("staff_disable", disabled.headers["X-Request-ID"]), ("staff_enable", enabled.headers["X-Request-ID"]),
        }
        assert all(log.actor_account_id == auth.account_id for log in logs)
        assert db.get_one(Account, account_id).status == "active"
        staff = db.get_one(StaffProfile, UUID(staff_id))
        assert staff.account_id == account_id and staff.disabled_at is None


def test_binding_fails_closed_when_redis_cannot_consume(
    auth: AuthFixture, wechat_codes: dict[str, str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    staff_id = open_staff(auth)
    qr = invitation(auth, staff_id)
    code = uuid4().hex
    wechat_codes[code] = uuid4().hex

    def unavailable(*args: object) -> None:
        raise ConnectionError("fixture Redis failure")

    monkeypatch.setattr(auth.service.cache, "eval", unavailable)
    assert_error(use_invite(auth, qr, code), 503, "AUTH_UNAVAILABLE")
    assert auth.client.get(f"{STAFF}/{staff_id}", headers=admin(auth)).json()["data"]["wechat_bound"] is False
