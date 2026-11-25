from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Connection, event, select
from sqlalchemy.orm import Mapper, Session

from app.db.models import Account, CustomerAssignment, Member, OperationLog, StaffProfile
from test_auth import AuthFixture, assert_error, auth, auth_infrastructure, bearer
from test_permissions import add_employee, add_member, phones

API = "/api/v1"
ASSIGNMENTS = f"{API}/admin/assignments"
CANDIDATES = f"{ASSIGNMENTS}/candidates"


def payload(staff_id: UUID, previous: UUID | str | None, reason: str = "确认归属") -> dict[str, str | None]:
    return {"to_staff_id": str(staff_id), "expected_assignment_id": str(previous) if previous else None, "reason": reason}


def test_assign_then_transfer_and_keep_history(auth: AuthFixture, phones: None) -> None:
    with Session(auth.engine) as db:
        first_account, first_staff = add_employee(db)
        next_account, next_staff = add_employee(db)
        manager, _ = add_employee(db, "manager")
        member = add_member(db)
        db.get_one(Member, member).source_employee_id = first_staff
        db.commit()
    admin_headers = bearer(auth.tokens.access_token)
    manager_headers = bearer(auth.service.issue(manager, "manager", "admin_web").access_token)
    first_headers = bearer(auth.service.issue(first_account, "employee", "miniprogram").access_token)
    next_headers = bearer(auth.service.issue(next_account, "employee", "miniprogram").access_token)
    detail = f"{API}/customers/{member}"
    transfer = f"{detail}/transfer"
    employee_list = f"{API}/staff/me/customers"

    assert auth.client.get(ASSIGNMENTS, headers=admin_headers, params={
        "member_id": str(member), "is_current": True,
    }).json()["data"]["items"] == []
    missing_expected = {"to_staff_id": str(first_staff), "reason": "初次分配"}
    assert_error(auth.client.post(transfer, headers=admin_headers, json=missing_expected), 422, "VALIDATION_ERROR")
    assert_error(auth.client.post(transfer, headers=admin_headers, json=payload(first_staff, None, "  ")),
                 422, "VALIDATION_ERROR")
    assert_error(auth.client.get(detail, headers=first_headers), 404, "NOT_FOUND")

    assigned = auth.client.post(transfer, headers=admin_headers, json=payload(first_staff, None, " 初次分配 "))
    assert assigned.status_code == 200
    data = assigned.json()["data"]
    initial = data["current_assignment"]
    assert data["previous_assignment_id"] is None
    assert initial["staff_id"] == str(first_staff) and initial["bind_source"] == "manual"
    assert initial["change_reason"] == "初次分配" and initial["operator_account_id"] == str(auth.account_id)
    assert initial["is_current"] is True and initial["ended_at"] is None and initial["started_at"].endswith("Z")
    assert auth.client.get(detail, headers=first_headers).status_code == 200
    assert_error(auth.client.get(detail, headers=next_headers), 404, "NOT_FOUND")
    assert_error(auth.client.post(transfer, headers=admin_headers, json=payload(first_staff, initial["id"])),
                 409, "ASSIGNMENT_UNCHANGED")
    assert_error(auth.client.post(transfer, headers=admin_headers, json=payload(next_staff, None)), 409, "ASSIGNMENT_CHANGED")

    moved = auth.client.post(transfer, headers=manager_headers, json=payload(next_staff, initial["id"], "交接"))
    assert moved.status_code == 200
    assert moved.json()["data"]["previous_assignment_id"] == initial["id"]
    replacement = moved.json()["data"]["current_assignment"]
    assert replacement["staff_id"] == str(next_staff) and replacement["bind_source"] == "admin_transfer"
    assert replacement["change_reason"] == "交接" and replacement["operator_account_id"] == str(manager)
    assert_error(auth.client.get(detail, headers=first_headers), 404, "NOT_FOUND")
    assert auth.client.get(detail, headers=next_headers).json()["data"]["current_staff_id"] == str(next_staff)
    assert auth.client.get(employee_list, headers=first_headers).json()["data"]["total"] == 0
    assert auth.client.get(employee_list, headers=next_headers).json()["data"]["items"][0]["id"] == str(member)
    assert_error(auth.client.post(transfer, headers=manager_headers, json=payload(first_staff, initial["id"])),
                 409, "ASSIGNMENT_CHANGED")

    query = {"member_id": str(member), "page_size": 1}
    first_page = auth.client.get(ASSIGNMENTS, headers=manager_headers, params=query)
    assert first_page.headers["cache-control"] == "no-store"
    assert first_page.json()["data"] == {"items": [replacement], "page": 1, "page_size": 1, "total": 2}
    previous = auth.client.get(ASSIGNMENTS, headers=manager_headers, params={**query, "page": 2}).json()["data"]["items"][0]
    assert previous == {**initial, "is_current": False, "ended_at": replacement["started_at"]}
    filtered = auth.client.get(ASSIGNMENTS, headers=admin_headers, params={
        **query, "staff_id": str(first_staff), "is_current": False,
    }).json()["data"]
    assert filtered["total"] == 1 and filtered["items"] == [previous]
    with Session(auth.engine) as db:
        assert db.get_one(Member, member).source_employee_id == first_staff
        logs = list(db.scalars(select(OperationLog).where(OperationLog.target_id == member).order_by(OperationLog.created_at)))
        assert [log.action for log in logs] == ["assign", "transfer"]
        assert (logs[0].actor_account_id, logs[0].actor_role) == (auth.account_id, "admin")
        assert (logs[1].actor_account_id, logs[1].actor_role) == (manager, "manager")
        assert [log.request_id for log in logs] == [assigned.headers["X-Request-ID"], moved.headers["X-Request-ID"]]
        assert all(log.target_type == "member" and log.module == "customer_assignments" for log in logs)
        assert logs[0].before_data is None
        assert logs[1].before_data == logs[0].after_data == {"assignment_id": initial["id"], "staff_id": str(first_staff)}
        assert logs[1].after_data == {"assignment_id": replacement["id"], "staff_id": str(next_staff)}


def test_candidates_enforce_staff_eligibility_and_r7(auth: AuthFixture, phones: None) -> None:
    keyword = uuid4().hex[:8]
    with Session(auth.engine) as db:
        account, employee = add_employee(db)
        _, inactive = add_employee(db)
        disabled_account, disabled = add_employee(db)
        _, other_role = add_employee(db, "manager")
        for id_ in (employee, inactive, disabled, other_role):
            db.get_one(StaffProfile, id_).display_name = keyword
        db.get_one(StaffProfile, inactive).status = "disabled"
        db.get_one(Account, disabled_account).status = "disabled"
        member = add_member(db, account_id=account)
        db.commit()
    admin_headers = bearer(auth.tokens.access_token)
    result = auth.client.get(CANDIDATES, headers=admin_headers, params={"q": keyword}).json()["data"]
    assert result["total"] == 1 and result["items"] == [{"id": str(employee), "display_name": keyword}]
    target = f"{API}/customers/{member}/transfer"
    for staff in (inactive, disabled, other_role, uuid4()):
        assert_error(auth.client.post(target, headers=admin_headers, json=payload(staff, None)),
                     422, "STAFF_NOT_ELIGIBLE")
    assert_error(auth.client.post(f"{API}/customers/{uuid4()}/transfer", headers=admin_headers, json=payload(employee, None)),
                 404, "NOT_FOUND")
    for role in ("member", "employee"):
        token = auth.service.issue(account, role, "miniprogram").access_token
        headers = {**bearer(token), "X-Role": "admin"}
        for route in (ASSIGNMENTS, CANDIDATES):
            assert_error(auth.client.get(route, headers=headers), 403, "FORBIDDEN")
        assert_error(auth.client.post(target, headers=headers, json=payload(employee, None)), 403, "FORBIDDEN")


@pytest.mark.parametrize("has_current", [False, True])
def test_concurrent_changes_only_one_wins(auth: AuthFixture, phones: None, has_current: bool) -> None:
    with Session(auth.engine) as db:
        _, first = add_employee(db)
        _, second = add_employee(db)
        _, original = add_employee(db)
        member = add_member(db)
        expected = None
        if has_current:
            old = CustomerAssignment(member_id=member, staff_id=original, bind_source="manual")
            db.add(old)
            db.flush()
            expected = old.id
        db.commit()
    start = Barrier(2, timeout=10)

    def submit(staff: UUID):
        start.wait()
        return auth.client.post(f"{API}/customers/{member}/transfer",
                                headers=bearer(auth.tokens.access_token), json=payload(staff, expected))

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(submit, (first, second)))
    assert sorted(response.status_code for response in responses) == [200, 409]
    assert_error(next(response for response in responses if response.status_code == 409), 409, "ASSIGNMENT_CHANGED")
    with Session(auth.engine) as db:
        rows = list(db.scalars(select(CustomerAssignment).where(CustomerAssignment.member_id == member)))
        assert len(rows) == (2 if has_current else 1)
        assert sum(row.is_current for row in rows) == 1
        assert len(list(db.scalars(select(OperationLog).where(OperationLog.target_id == member)))) == 1


def test_audit_write_failure_rolls_back_assignment(auth: AuthFixture, phones: None) -> None:
    with Session(auth.engine) as db:
        _, first = add_employee(db)
        _, second = add_employee(db)
        member = add_member(db)
        original = CustomerAssignment(member_id=member, staff_id=first, bind_source="manual")
        db.add(original)
        db.flush()
        previous_id = original.id
        db.commit()

    def reject_audit(mapper: Mapper[OperationLog], connection: Connection, log: OperationLog) -> None:
        if log.target_id == member:
            raise RuntimeError("simulated audit write failure")

    event.listen(OperationLog, "before_insert", reject_audit)
    try:
        response = auth.client.post(f"{API}/customers/{member}/transfer",
                                    headers=bearer(auth.tokens.access_token), json=payload(second, previous_id))
    finally:
        event.remove(OperationLog, "before_insert", reject_audit)
    assert_error(response, 500, "INTERNAL_ERROR")
    with Session(auth.engine) as db:
        row = db.scalars(select(CustomerAssignment).where(CustomerAssignment.member_id == member)).one()
        assert row.id == previous_id and row.staff_id == first and row.is_current and row.ended_at is None
        assert db.scalar(select(OperationLog).where(OperationLog.target_id == member)) is None
