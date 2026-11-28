import socket
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Event
from uuid import UUID

import pytest
from redis import Redis
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.db.models import CustomerAssignment, CustomerStatus, FollowupRecord, Member, OperationLog
from test_auth import AuthFixture, assert_error, auth, auth_infrastructure, bearer
from test_permissions import add_employee, add_member, phones

TASKS = "/api/v1/followup-tasks"
ADMIN = "/api/v1/admin/followups"
RESULT = {"result": "验收测试联络结果"}


@dataclass
class Scenario:
    member: UUID
    assignment: UUID
    first: UUID
    second: UUID
    employee: dict[str, str]
    other: dict[str, str]
    member_auth: dict[str, str]
    manager: dict[str, str]
    admin: dict[str, str]

    @property
    def records(self) -> str:
        return f"/api/v1/customers/{self.member}/followups"

    def task_body(self, staff: UUID | None = None) -> dict[str, str]:
        return {"member_id": str(self.member), "assigned_staff_id": str(staff or self.first),
                "title": "测试回访", "scheduled_at": "2030-04-05T09:00:00+08:00"}


@pytest.fixture
def scenario(auth: AuthFixture, phones: None) -> Scenario:
    with Session(auth.engine) as db:
        first_account, first = add_employee(db)
        second_account, second = add_employee(db)
        manager, _ = add_employee(db, "manager")
        member = add_member(db, account_id=first_account)
        row = CustomerAssignment(member_id=member, staff_id=first, bind_source="manual")
        db.add(row)
        db.flush()
        assignment = row.id
        db.commit()
    return Scenario(
        member, assignment, first, second,
        bearer(auth.service.issue(first_account, "employee", "miniprogram").access_token),
        bearer(auth.service.issue(second_account, "employee", "miniprogram").access_token),
        bearer(auth.service.issue(first_account, "member", "miniprogram").access_token),
        bearer(auth.service.issue(manager, "manager", "admin_web").access_token),
        bearer(auth.tokens.access_token),
    )


def create_task(auth: AuthFixture, scenario: Scenario) -> str:
    response = auth.client.post(TASKS, headers=scenario.manager, json=scenario.task_body())
    assert response.status_code == 201, response.text
    return str(response.json()["data"]["id"])


def test_records_and_home_filter(auth: AuthFixture, scenario: Scenario) -> None:
    req = auth.client
    for kind in ("phone", "home_visit"):
        response = req.post(scenario.records, headers=scenario.employee, json={
            "contact_type": kind, "content": "测试沟通内容", "next_followup_at": "2030-04-06T09:00:00+08:00",
            "effective_contact": kind == "phone", "followup_at": "2030-04-05T09:00:00+08:00",
        })
        assert response.status_code == 201, response.text
        assert response.json()["data"]["staff_id"] == str(scenario.first)
    with Session(auth.engine) as db:
        last_contact = db.scalar(select(CustomerStatus.last_effective_contact_at).where(
            CustomerStatus.member_id == scenario.member,
        ))
        assert last_contact == datetime(2030, 4, 5, 1, tzinfo=UTC)

    assert req.get(TASKS, headers=scenario.employee).json()["data"]["total"] == 0
    home = req.get(scenario.records, headers=scenario.employee, params={"contact_type": "home_visit"})
    assert [row["contact_type"] for row in home.json()["data"]["items"]] == ["home_visit"]
    assert_error(req.get(scenario.records, headers=scenario.other), 404, "NOT_FOUND")
    for role in (scenario.admin, scenario.manager):
        records = req.get(ADMIN, headers=role, params={"member_id": str(scenario.member), "page_size": 1})
        assert records.json()["data"]["total"] == 2
        assert len(records.json()["data"]["items"]) == 1
    assert req.post(scenario.records, headers=scenario.employee, json={
        "contact_type": "phone", "content": "测试", "staff_id": str(scenario.second),
    }).status_code == 422


def test_task_roles_and_transfer(auth: AuthFixture, scenario: Scenario) -> None:
    req = auth.client
    task = create_task(auth, scenario)
    assert req.get(TASKS, headers=scenario.employee).json()["data"]["items"][0]["id"] == task
    assert req.get(TASKS, headers=scenario.other).json()["data"]["total"] == 0
    assert_error(req.post(f"{TASKS}/{task}/complete", headers=scenario.other, json=RESULT), 404, "NOT_FOUND")
    for path in (scenario.records, TASKS, ADMIN):
        assert_error(req.get(path, headers=scenario.member_auth), 403, "FORBIDDEN")
    assert_error(req.post(TASKS, headers=scenario.employee, json=scenario.task_body()), 403, "FORBIDDEN")
    assert_error(req.post(TASKS, headers=scenario.admin, json=scenario.task_body(scenario.second)), 409, "ASSIGNMENT_CHANGED")
    assert req.post(f"/api/v1/customers/{scenario.member}/transfer", headers=scenario.admin, json={
        "to_staff_id": str(scenario.second), "expected_assignment_id": str(scenario.assignment), "reason": "验收",
    }).is_success
    assert_error(req.post(scenario.records, headers=scenario.employee, json={
        "contact_type": "phone", "content": "不可写入",
    }), 404, "NOT_FOUND")
    for employee in (scenario.employee, scenario.other):
        assert req.get(TASKS, headers=employee).json()["data"]["total"] == 0
        assert_error(req.post(f"{TASKS}/{task}/complete", headers=employee, json=RESULT), 404, "NOT_FOUND")
    for role in (scenario.admin, scenario.manager):
        assert any(row["id"] == task for row in req.get(TASKS, headers=role).json()["data"]["items"])
    assert req.post(f"{TASKS}/{task}/ignore", headers=scenario.manager, json=RESULT).json()["data"]["status"] == "ignored"
    assert_error(req.post(f"{TASKS}/{task}/ignore", headers=scenario.admin, json=RESULT), 409, "TASK_TERMINAL")
    new = req.post(TASKS, headers=scenario.admin, json=scenario.task_body(scenario.second))
    assert new.status_code == 201, new.text
    assert req.get(TASKS, headers=scenario.other).json()["data"]["items"][0]["id"] == new.json()["data"]["id"]


def test_postpone_twice_and_concurrent_terminal_update(auth: AuthFixture, scenario: Scenario) -> None:
    path = f"{TASKS}/{create_task(auth, scenario)}"
    for day in (6, 7):
        postponed = auth.client.post(path + "/postpone", headers=scenario.employee, json={
            "postponed_until": f"2030-04-0{day}T09:00:00+08:00",
        })
        assert postponed.json()["data"]["planned_at"] == f"2030-04-0{day}T01:00:00Z"
    assert auth.client.get(TASKS, headers=scenario.employee).json()["data"]["total"] == 1
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = [pool.submit(auth.client.post, path + "/complete", headers=scenario.employee, json=RESULT) for _ in range(2)]
        assert sorted(request.result().status_code for request in pending) == [200, 409]
    assert_error(auth.client.post(path + "/postpone", headers=scenario.employee, json={
        "postponed_until": "2030-04-08T09:00:00+08:00",
    }), 409, "TASK_TERMINAL")


def test_followup_waits_for_transfer_lock(auth: AuthFixture, scenario: Scenario) -> None:
    waiting = Event()

    def before_query(conn, cursor, statement, parameters, context, executemany):
        if "FROM members" in statement and "FOR UPDATE" in statement:
            waiting.set()

    with Session(auth.engine) as db, ThreadPoolExecutor(max_workers=1) as pool:
        db.scalar(select(Member.id).where(Member.id == scenario.member).with_for_update())
        event.listen(auth.engine, "before_cursor_execute", before_query)
        try:
            request = pool.submit(auth.client.post, scenario.records, headers=scenario.employee,
                                  json={"contact_type": "phone", "content": "不能提交"})
            assert waiting.wait(5)
            original = db.get_one(CustomerAssignment, scenario.assignment)
            original.is_current = False
            original.ended_at = datetime.now(UTC)
            db.flush()
            db.add(CustomerAssignment(member_id=scenario.member, staff_id=scenario.second, bind_source="admin_transfer"))
            db.commit()
            assert_error(request.result(timeout=10), 404, "NOT_FOUND")
        finally:
            db.rollback()
            event.remove(auth.engine, "before_cursor_execute", before_query)


def test_audit_is_redacted_and_failure_rolls_back(auth: AuthFixture, scenario: Scenario) -> None:
    body = {"contact_type": "phone", "content": "测试敏感内容不得进入审计"}
    response = auth.client.post(scenario.records, headers=scenario.employee, json=body)
    assert response.status_code == 201, response.text
    with Session(auth.engine) as db:
        audit = db.scalars(select(OperationLog).where(OperationLog.request_id == response.headers["X-Request-ID"])).one()
        assert audit.after_data == {"contact_type": "phone"}
        assert audit.actor_role == "employee"
    def fail(mapper, connection, target):
        raise RuntimeError("audit write failed")
    event.listen(OperationLog, "before_insert", fail)
    try:
        assert auth.client.post(scenario.records, headers=scenario.employee, json=body).status_code == 500
    finally:
        event.remove(OperationLog, "before_insert", fail)
    with Session(auth.engine) as db:
        assert len(db.scalars(select(FollowupRecord).where(FollowupRecord.member_id == scenario.member)).all()) == 1

def test_unavailable_redis_fails_closed(auth: AuthFixture, scenario: Scenario, monkeypatch: pytest.MonkeyPatch) -> None:
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        with Redis(host="127.0.0.1", port=reserved.getsockname()[1], socket_connect_timeout=0.2) as cache:
            monkeypatch.setattr(auth.service, "cache", cache)
            assert_error(auth.client.get(TASKS, headers=scenario.employee), 503, "AUTH_UNAVAILABLE")
            assert_error(auth.client.post(scenario.records, headers=scenario.employee, json={
                "contact_type": "phone", "content": "不可写入",
            }), 503, "AUTH_UNAVAILABLE")
    with Session(auth.engine) as db:
        assert db.scalar(select(FollowupRecord.id).where(FollowupRecord.member_id == scenario.member)) is None
