from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, field_serializer
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.auth.identity import Identity
from app.db.models import Account, CustomerAssignment, Member, OperationLog, StaffProfile
from app.http import APIError


class AssignmentView(BaseModel):
    id: UUID
    member_id: UUID
    staff_id: UUID
    staff_name: str
    is_current: bool
    bind_source: str
    started_at: datetime
    ended_at: datetime | None
    change_reason: str | None
    operator_account_id: UUID | None

    @field_serializer("started_at", "ended_at", when_used="json")
    def utc_time(self, value: datetime | None) -> datetime | None:
        return value.astimezone(UTC) if value is not None else None

    @classmethod
    def from_record(cls, record: CustomerAssignment, staff_name: str) -> "AssignmentView":
        return cls(
            id=record.id, member_id=record.member_id, staff_id=record.staff_id, staff_name=staff_name,
            is_current=record.is_current, bind_source=record.bind_source, started_at=record.started_at,
            ended_at=record.ended_at, change_reason=record.change_reason, operator_account_id=record.operator_account_id,
        )


class AssignmentCandidate(BaseModel):
    id: UUID
    display_name: str


class TransferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to_staff_id: UUID
    expected_assignment_id: UUID | None
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class TransferResult(BaseModel):
    current_assignment: AssignmentView
    previous_assignment_id: UUID | None


def eligible_employees() -> Select[StaffProfile]:
    return (
        select(StaffProfile)
        .join(Account, Account.id == StaffProfile.account_id)
        .where(
            StaffProfile.role == "employee", StaffProfile.status == "active",
            StaffProfile.disabled_at.is_(None), Account.status == "active",
        )
    )


def change_assignment(
    db: Session, member_id: UUID, body: TransferRequest, actor: Identity, request_id: str,
) -> TransferResult:
    assert actor.selected_role in ("admin", "manager")
    # Lock the member even if there is no current row, so first assignments also serialize.
    if db.scalar(select(Member.id).where(Member.id == member_id).with_for_update()) is None:
        raise APIError(404, "NOT_FOUND", "会员不存在")
    previous = db.scalar(select(CustomerAssignment).where(
        CustomerAssignment.member_id == member_id, CustomerAssignment.is_current.is_(True),
    ))
    previous_id = previous.id if previous is not None else None
    if previous_id != body.expected_assignment_id:
        raise APIError(409, "ASSIGNMENT_CHANGED", "客户归属已变化，请刷新后重试")
    if previous is not None and previous.staff_id == body.to_staff_id:
        raise APIError(409, "ASSIGNMENT_UNCHANGED", "该员工已是当前负责人")
    target = db.scalar(eligible_employees().where(StaffProfile.id == body.to_staff_id).with_for_update(read=True))
    if target is None:
        raise APIError(422, "STAFF_NOT_ELIGIBLE", "请选择在职且账号启用的员工")

    changed_at = datetime.now(UTC)
    if previous is not None:
        previous.is_current = False
        previous.ended_at = changed_at
        # Release the partial unique index entry before inserting the replacement.
        db.flush()
    assignment = CustomerAssignment(
        member_id=member_id, staff_id=target.id, is_current=True,
        bind_source="manual" if previous is None else "admin_transfer",
        started_at=changed_at, change_reason=body.reason, operator_account_id=actor.account_id,
    )
    db.add(assignment)
    db.flush()
    db.add(OperationLog(
        actor_account_id=actor.account_id, actor_role=actor.selected_role,
        module="customer_assignments", action="assign" if previous is None else "transfer",
        target_type="member", target_id=member_id,
        before_data={"assignment_id": str(previous_id), "staff_id": str(previous.staff_id)} if previous else None,
        after_data={"assignment_id": str(assignment.id), "staff_id": str(target.id)},
        request_id=request_id, created_at=changed_at,
    ))
    result = TransferResult(
        current_assignment=AssignmentView.from_record(assignment, target.display_name), previous_assignment_id=previous_id,
    )
    db.commit()
    return result
