from uuid import UUID

from sqlalchemy import ColumnElement, select, true
from sqlalchemy.orm import Session

from app.auth.identity import Identity, Role
from app.auth.permissions import check_permission
from app.db.models import CustomerAssignment, ExchangeOrder, FollowupTask, Member, StaffProfile
from app.http import APIError


def _staff_id(identity: Identity, role: Role) -> ColumnElement[UUID]:
    return select(StaffProfile.id).where(
        StaffProfile.account_id == identity.account_id, StaffProfile.role == role,
        StaffProfile.status == "active", StaffProfile.disabled_at.is_(None),
    ).scalar_subquery()


def customer_scope(identity: Identity) -> ColumnElement[bool]:
    check_permission("R6", identity.selected_role)
    if identity.selected_role != "employee":
        return true()
    return current_customer_assignment(_staff_id(identity, "employee"))


def current_customer_assignment(staff_id: UUID | ColumnElement[UUID]) -> ColumnElement[bool]:
    return select(CustomerAssignment.id).where(
        CustomerAssignment.member_id == Member.id, CustomerAssignment.is_current.is_(True),
        CustomerAssignment.staff_id == staff_id,
    ).correlate(Member).exists()


def own_customer_scope(identity: Identity) -> ColumnElement[bool]:
    check_permission("R6", identity.selected_role)
    assert identity.selected_role is not None
    return current_customer_assignment(_staff_id(identity, identity.selected_role))


def task_scope(identity: Identity) -> ColumnElement[bool]:
    check_permission("R8", identity.selected_role)
    if identity.selected_role != "employee":
        return true()
    return (
        (FollowupTask.assigned_staff_id == _staff_id(identity, "employee"))
        & select(CustomerAssignment.id).where(
            CustomerAssignment.member_id == FollowupTask.member_id,
            CustomerAssignment.is_current.is_(True),
            CustomerAssignment.staff_id == FollowupTask.assigned_staff_id,
        ).correlate(FollowupTask).exists()
    )


def require_task_access(db: Session, identity: Identity, task_id: UUID) -> FollowupTask:
    task = db.scalar(select(FollowupTask).where(FollowupTask.id == task_id, task_scope(identity)))
    if task is None:
        raise APIError(404, "NOT_FOUND", "任务不存在")
    return task


def owned_order(db: Session, identity: Identity, order_id: UUID) -> ExchangeOrder:
    check_permission("R2", identity.selected_role)
    order = db.scalar(
        select(ExchangeOrder).join(Member).where(
            ExchangeOrder.id == order_id, Member.account_id == identity.account_id, Member.status == "active",
        ),
    )
    if order is None:
        raise APIError(404, "NOT_FOUND", "订单不存在")
    return order
