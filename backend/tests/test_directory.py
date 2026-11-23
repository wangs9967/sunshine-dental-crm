import logging
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.auth.identity import Role
from app.db.models import CustomerAssignment, Member, StaffProfile
from app.http import DirectoryAccessLogFilter
from test_auth import AuthFixture, assert_error, auth, auth_infrastructure, bearer
from test_permissions import add_employee, add_member, phones

API = "/api/v1"


@pytest.mark.parametrize("role", ["manager", "admin"])
def test_management_directories(auth: AuthFixture, phones: None, role: Role) -> None:
    prefix = uuid4().hex[:12]
    with Session(auth.engine) as db:
        manager, _ = add_employee(db, role)
        _, first_staff = add_employee(db)
        _, second_staff = add_employee(db)
        employee = db.get_one(StaffProfile, second_staff)
        employee.employee_no = f"{prefix}-S"
        employee.display_name = f"{prefix}员工"
        employee.status = "disabled"
        db.get_one(StaffProfile, first_staff).display_name = "首次来源"
        first, second = add_member(db), add_member(db)
        first_member = db.get_one(Member, first)
        first_member.source_employee_id = first_staff
        first_member.name = f"{prefix}会员"
        first_member.member_no = f"{prefix}-M1"
        second_member = db.get_one(Member, second)
        second_member.name = f"{prefix}会员"
        second_member.member_no = f"{prefix}-M2"
        second_member.status = "disabled"
        db.add_all([
            CustomerAssignment(member_id=first, staff_id=first_staff, bind_source="manual", is_current=False,
                               ended_at=datetime.now(UTC)),
            CustomerAssignment(member_id=first, staff_id=second_staff, bind_source="admin_transfer"),
        ])
        db.commit()
    headers = bearer(auth.service.issue(manager, role, "admin_web").access_token)
    members = f"{API}/admin/members"
    staff = f"{API}/admin/staff"
    first_page = auth.client.get(members, headers=headers, params={"q": prefix, "page_size": 1})
    assert first_page.headers["cache-control"] == "no-store"
    first_result = first_page.json()["data"]
    second_result = auth.client.get(members, headers=headers, params={
        "q": prefix, "page_size": 1, "page": 2,
    }).json()["data"]
    assert first_result["total"] == second_result["total"] == 2
    assert first_result["items"][0]["id"] != second_result["items"][0]["id"]
    assert auth.client.get(members, headers=headers, params={"q": prefix + "-M1"}).json()["data"]["total"] == 1
    for q, count in [("19900000000", 1), ("1990000", 0), ("19900000001", 0)]:
        response = auth.client.get(members, headers=headers, params={"q": q, "staff_id": str(second_staff)})
        assert response.json()["data"]["total"] == count
        assert "19900000000" not in response.text
    filtered = auth.client.get(members, headers=headers, params={
        "q": prefix, "status": "disabled",
    }).json()["data"]["items"]
    assert [row["id"] for row in filtered] == [str(second)]
    old_scope = auth.client.get(members, headers=headers, params={"staff_id": str(first_staff)}).json()["data"]
    assert old_scope["total"] == 0
    detail = auth.client.get(f"{members}/{first}", headers=headers)
    data = detail.json()["data"]
    assert data["phone_masked"] == "199****0000"
    assert data["source_employee_id"] == str(first_staff) and data["source_employee_name"] == "首次来源"
    assert data["current_staff_id"] == str(second_staff) and data["current_staff_name"] == f"{prefix}员工"
    assert data["visit_status"] == "not_visited"
    assert {"phone", "phone_ciphertext", "phone_search_hash"}.isdisjoint(data)
    for keyword in (prefix + "-S", prefix + "员工"):
        result = auth.client.get(staff, headers=headers, params={
            "q": keyword, "role": "employee", "status": "disabled",
        }).json()["data"]
        assert result["total"] == 1
        assert result["items"][0]["id"] == str(second_staff)
    assert auth.client.get(staff, headers=headers, params={"q": prefix, "role": "manager"}).json()["data"]["total"] == 0
    staff_detail = auth.client.get(f"{staff}/{second_staff}", headers=headers)
    assert set(staff_detail.json()["data"]) == {"id", "employee_no", "display_name", "role", "status"}
    for base in (members, staff):
        assert_error(auth.client.get(f"{base}/{uuid4()}", headers=headers), 404, "NOT_FOUND")
        assert_error(auth.client.get(base, headers=headers, params={"page_size": 101}), 422, "VALIDATION_ERROR")


def test_customer_list_scope_filters_and_transfer(auth: AuthFixture, phones: None) -> None:
    with Session(auth.engine) as db:
        first_account, staff = add_employee(db)
        second_account, other_staff = add_employee(db)
        first = add_member(db, account_id=first_account)
        second = add_member(db)
        assignment = CustomerAssignment(member_id=first, staff_id=staff, bind_source="manual")
        db.add_all([assignment, CustomerAssignment(member_id=second, staff_id=other_staff, bind_source="manual")])
        db.flush()
        assignment_id = assignment.id
        db.commit()
    url = f"{API}/staff/me/customers"
    employee = bearer(auth.service.issue(first_account, "employee", "miniprogram").access_token)
    other = bearer(auth.service.issue(second_account, "employee", "miniprogram").access_token)
    member = bearer(auth.service.issue(first_account, "member", "miniprogram").access_token)
    result = auth.client.get(url, headers=employee, params={
        "q": "测试会员", "visit_status": "not_visited", "consume_status": "not_consumed", "deal_status": "not_dealt",
        "role": "admin", "account_id": str(second_account),
    }).json()["data"]
    assert result["total"] == 1 and result["items"][0]["id"] == str(first)
    for field, value in [("visit_status", "visited"), ("consume_status", "consumed"), ("deal_status", "dealt")]:
        assert auth.client.get(url, headers=employee, params={field: value}).json()["data"]["total"] == 0
    assert_error(auth.client.get(f"{API}/customers/{second}", headers=employee), 404, "NOT_FOUND")
    for path in ("admin/members", f"admin/members/{first}", "admin/staff", f"admin/staff/{staff}"):
        assert_error(auth.client.get(f"{API}/{path}", headers=employee), 403, "FORBIDDEN")
        assert_error(auth.client.get(f"{API}/{path}", headers=member), 403, "FORBIDDEN")
    assert_error(auth.client.get(url, headers=member), 403, "FORBIDDEN")
    assert_error(auth.client.get(url), 401, "INVALID_SESSION")
    with Session(auth.engine) as db:
        previous = db.get_one(CustomerAssignment, assignment_id)
        previous.is_current = False
        previous.ended_at = datetime.now(UTC)
        db.flush()
        db.add(CustomerAssignment(member_id=first, staff_id=other_staff, bind_source="admin_transfer"))
        db.commit()
    assert auth.client.get(url, headers=employee).json()["data"]["total"] == 0
    assert_error(auth.client.get(f"{API}/customers/{first}", headers=employee), 404, "NOT_FOUND")
    assert auth.client.get(url, headers=other).json()["data"]["total"] == 2


@pytest.mark.parametrize("route", ["/admin/members", "/staff/me/customers"])
def test_directory_access_log_redacts_query(route: str) -> None:
    record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %s', (
        "127.0.0.1", "GET", f"{API}{route}?q=19900000000&page=1", "1.1", 200,
    ), None)
    assert DirectoryAccessLogFilter().filter(record)
    assert record.getMessage() == f'127.0.0.1 - "GET {API}{route} HTTP/1.1" 200'
