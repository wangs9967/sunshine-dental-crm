import secrets
from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID, uuid4

import pytest
from fastapi import Depends, Request
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import Role, resolve_identity
from app.auth.permissions import Permission, check_permission
from app.auth.phone import protect_phone
from app.auth.routes import Authenticated, require_permission
from app.auth.scopes import require_task_access, task_scope
from app.db.models import (
    Account, CustomerAssignment, CustomerStatus, ExchangeOrder, FollowupTask, Member, OperationLog, Product, StaffProfile,
)
from app.http import APIError, success
from app.main import app
from test_auth import AuthFixture, assert_error, auth, auth_infrastructure, bearer

API = "/api/v1"
EXPECTED: dict[Permission, set[Role | None]] = {
    "R1": {None}, "R2": {"member"}, "R3": set(), "R4": {"member"}, "R5": {"employee", "manager", "admin"},
    "R6": {"employee", "manager", "admin"}, "R7": {"manager", "admin"}, "R8": {"employee", "manager", "admin"},
    "R9": {"manager", "admin"}, "R10": {"manager", "admin"}, "R11": {"manager", "admin"},
    "R12": {"manager", "admin"}, "R13": set(), "R14": set(), "R15": {"admin"}, "R16": {"admin"},
    "R17": {"admin"}, "R17_WRITE": set(), "R18": {"admin"}, "R18_WRITE": set(),
}


@pytest.mark.parametrize("role", [None, "member", "employee", "manager", "admin"])
def test_fixed_role_matrix(role: Role | None) -> None:
    for permission, allowed in EXPECTED.items():
        if role in allowed:
            check_permission(permission, role)
        else:
            with pytest.raises(APIError) as denied:
                check_permission(permission, role)
            assert denied.value.status == 403, permission


def add_employee(db: Session, role: str = "employee") -> tuple[UUID, UUID]:
    account = Account(wechat_openid=uuid4().hex)
    db.add(account)
    db.flush()
    staff = StaffProfile(account_id=account.id, role=role, display_name="测试员工")
    db.add(staff)
    db.flush()
    return account.id, staff.id


def add_member(db: Session, *, account_id: UUID | None = None) -> UUID:
    if account_id is None:
        account = Account(wechat_openid=uuid4().hex)
        db.add(account)
        db.flush()
        account_id = account.id
    settings = app.state.auth_settings
    phone, digest = protect_phone("19900000000", settings)
    member = Member(
        account_id=account_id, name="测试会员", member_no=uuid4().hex, birthday=date(2000, 1, 1),
        phone_ciphertext=phone, phone_search_hash=digest, register_source="direct",
    )
    db.add(member)
    db.flush()
    db.add(CustomerStatus(member_id=member.id))
    return member.id


@pytest.fixture
def phones(auth: AuthFixture) -> None:
    app.state.auth_settings.phone_encryption_key = SecretStr(secrets.token_urlsafe(32) + "=")
    app.state.auth_settings.phone_lookup_hmac_key = SecretStr(secrets.token_urlsafe(32) + "=")


def test_employee_current_assignment_and_immediate_transfer(auth: AuthFixture, phones: None) -> None:
    with Session(auth.engine) as db:
        first, first_staff = add_employee(db)
        second, second_staff = add_employee(db)
        customer = add_member(db, account_id=first)
        assignment = CustomerAssignment(member_id=customer, staff_id=first_staff, bind_source="manual")
        db.add(assignment)
        db.flush()
        assignment_id = assignment.id
        db.commit()

    first_headers = bearer(auth.service.issue(first, "employee", "miniprogram").access_token)
    second_headers = bearer(auth.service.issue(second, "employee", "miniprogram").access_token)
    member_headers = bearer(auth.service.issue(first, "member", "miniprogram").access_token)
    target = f"{API}/customers/{customer}"
    owned = auth.client.get(target, headers=first_headers)
    assert owned.is_success
    assert owned.json()["data"]["current_staff_id"] == str(first_staff)
    assert owned.json()["data"]["phone_masked"] == "199****0000"
    other = auth.client.get(target, headers={
        **second_headers, "X-Role": "admin", "X-Account-ID": str(first),
    }, params={"role": "manager", "account_id": str(first), "member_id": str(customer)})
    assert_error(other, 404, "NOT_FOUND")
    missing = auth.client.get(f"{API}/customers/{uuid4()}", headers=second_headers)
    assert other.json()["error"] == missing.json()["error"]
    assert_error(auth.client.get(target, headers=member_headers), 403, "FORBIDDEN")
    assert auth.client.get(f"{API}/auth/me", headers=member_headers).json()["data"]["available_roles"] == ["member"]
    assert auth.client.get(f"{API}/auth/me", headers=first_headers).json()["data"]["available_roles"] == ["employee"]
    assert auth.client.get(f"{API}/members/me", headers=member_headers).json()["data"]["id"] == str(customer)
    assert_error(auth.client.get(f"{API}/members/me", headers=first_headers), 403, "FORBIDDEN")

    with Session(auth.engine) as db:
        current = db.get_one(CustomerAssignment, assignment_id)
        current.is_current = False
        current.ended_at = datetime.now(UTC)
        db.flush()
        db.add(CustomerAssignment(member_id=customer, staff_id=second_staff, bind_source="admin_transfer"))
        db.commit()
    assert_error(auth.client.get(target, headers=first_headers), 404, "NOT_FOUND")
    assert auth.client.get(target, headers=second_headers).json()["data"]["current_staff_id"] == str(second_staff)

    with Session(auth.engine) as db:
        db.get_one(StaffProfile, second_staff).role = "manager"
        db.commit()
    assert_error(auth.client.get(target, headers=second_headers), 401, "INVALID_SESSION")


@pytest.mark.parametrize("role", ["manager", "admin"])
def test_management_reads_unassigned_and_other_staff_customers(auth: AuthFixture, phones: None, role: Role) -> None:
    with Session(auth.engine) as db:
        manager, _ = add_employee(db, role)
        _, employee = add_employee(db)
        assigned = add_member(db)
        unassigned = add_member(db)
        db.add(CustomerAssignment(member_id=assigned, staff_id=employee, bind_source="manual"))
        db.commit()
    headers = bearer(auth.service.issue(manager, role, "admin_web").access_token)
    assert auth.client.get(f"{API}/customers/{assigned}", headers=headers).json()["data"]["current_staff_id"] == str(employee)
    assert auth.client.get(f"{API}/customers/{unassigned}", headers=headers).json()["data"]["current_staff_id"] is None


def test_employee_task_scope_requires_both_assignee_and_current_customer(auth: AuthFixture, phones: None) -> None:
    with Session(auth.engine) as db:
        account, staff = add_employee(db)
        _, other_staff = add_employee(db)
        mine, theirs = add_member(db), add_member(db)
        db.add_all([
            CustomerAssignment(member_id=mine, staff_id=staff, bind_source="manual"),
            CustomerAssignment(member_id=theirs, staff_id=other_staff, bind_source="manual"),
        ])
        tasks = [
            FollowupTask(
                member_id=member, assigned_staff_id=assignee, task_type="manual", title="测试任务",
                scheduled_at=datetime.now(UTC), dedupe_key=uuid4().hex,
            )
            for member, assignee in ((mine, staff), (mine, other_staff), (theirs, staff))
        ]
        db.add_all(tasks)
        db.flush()
        task_ids = [task.id for task in tasks]
        db.commit()

        identity = resolve_identity(db, account, "employee", "miniprogram")
        assert identity is not None
        statement = select(FollowupTask.id).where(FollowupTask.id.in_(task_ids), task_scope(identity))
        assert db.scalars(statement).all() == [task_ids[0]]
        assert require_task_access(db, identity, task_ids[0]).id == task_ids[0]
        for invisible in task_ids[1:]:
            with pytest.raises(APIError) as denied:
                require_task_access(db, identity, invisible)
            assert denied.value.status == 404 and denied.value.code == "NOT_FOUND"
        admin = resolve_identity(db, auth.account_id, "admin", "admin_web")
        assert admin is not None
        assert set(db.scalars(select(FollowupTask.id).where(
            FollowupTask.id.in_(task_ids), task_scope(admin),
        ))) == set(task_ids)


def test_member_order_lookup_never_uses_supplied_member_id(auth: AuthFixture, phones: None) -> None:
    with Session(auth.engine) as db:
        account, _ = add_employee(db)
        own_member = add_member(db, account_id=account)
        other_member = add_member(db)
        product = Product(name="测试商品", points_price=3)
        db.add(product)
        db.flush()
        orders = [ExchangeOrder(
            member_id=member, product_id=product.id, order_no=uuid4().hex, product_snapshot={"name": "测试商品"},
                points_cost_total=3, idempotency_key=uuid4().hex, request_fingerprint=bytes(32),
                created_at=datetime.now(UTC),
        ) for member in (own_member, other_member)]
        db.add_all(orders)
        db.flush()
        mine, theirs = (order.id for order in orders)
        db.commit()
    headers = bearer(auth.service.issue(account, "member", "miniprogram").access_token)
    response = auth.client.get(f"{API}/exchange-orders/{mine}", headers=headers, params={"member_id": other_member})
    assert response.is_success
    data = response.json()["data"]
    assert data["id"] == str(mine) and data["points_cost_total"] == "3"
    assert set(data) == {"id", "order_no", "product_id", "product_snapshot", "quantity",
                         "points_cost_total", "status", "created_at", "verified_at"}
    assert_error(auth.client.get(f"{API}/exchange-orders/{theirs}", headers=headers),
                 404, "NOT_FOUND")
    assert_error(auth.client.get(f"{API}/exchange-orders/{mine}", headers=bearer(auth.tokens.access_token)),
                 403, "FORBIDDEN")


@pytest.mark.parametrize(("permission", "role", "code"), [
    ("R10", "employee", "FEATURE_NOT_AVAILABLE"),
    ("R13", "manager", "FEATURE_NOT_AVAILABLE"),
    ("R13", "admin", "FEATURE_NOT_AVAILABLE"),
    ("R14", "admin", "FEATURE_NOT_AVAILABLE"),
    ("R15", "manager", "FEATURE_NOT_AVAILABLE"),
    ("R16", "manager", "FEATURE_NOT_AVAILABLE"),
    ("R17_WRITE", "admin", "FEATURE_NOT_AVAILABLE"),
    ("R18_WRITE", "admin", "FORBIDDEN"),
])
def test_denied_write_audits_without_request_body(
    auth: AuthFixture, monkeypatch: pytest.MonkeyPatch, permission: Permission, role: Role, code: str,
) -> None:
    # Exercise the production dependency over HTTP without mounting unfinished business actions.
    monkeypatch.setattr(app.router, "routes", list(app.router.routes))
    guard = require_permission(permission)

    @app.post("/test-permission")
    def protected(request: Request, session: Annotated[Authenticated, Depends(guard)]) -> object:
        return success(request, {"role": session.identity.selected_role})

    with Session(auth.engine) as db:
        actor, _ = add_employee(db, role)
        db.commit()
    token = auth.service.issue(actor, role, "miniprogram" if role == "employee" else "admin_web").access_token
    response = auth.client.post("/test-permission", headers=bearer(token), json={"credential": "fixture-only"})
    assert_error(response, 403, code)
    with Session(auth.engine) as db:
        audit = db.scalars(select(OperationLog).where(OperationLog.request_id == response.headers["X-Request-ID"])).one()
        assert audit.actor_account_id == actor and audit.actor_role == role
        assert audit.action == "permission_denied" and audit.summary == code
        channel = "miniprogram" if role == "employee" else "admin_web"
        assert audit.after_data == {"permission": permission, "channel": channel}
        assert audit.before_data is None
