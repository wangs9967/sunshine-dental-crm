import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import ColumnElement, Select, and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.auth.member import MemberView
from app.auth.phone import phone_search_digest, read_masked_phone
from app.config import AuthSettings
from app.db.models import CustomerAssignment, CustomerStatus, Member, StaffProfile
from app.http import APIError


class Page[T](BaseModel):
    items: list[T]
    page: int
    page_size: int
    total: int


class StaffView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_no: str | None
    display_name: str
    role: str
    status: str


class CustomerView(MemberView):
    visit_status: str
    consume_status: str
    deal_status: str
    last_effective_contact_at: datetime | None
    next_recall_at: datetime | None
    current_staff_id: UUID | None


class AdminMemberView(MemberView):
    source_employee_id: UUID | None
    source_employee_name: str | None
    current_staff_id: UUID | None
    current_staff_name: str | None
    visit_status: str | None
    consume_status: str | None
    deal_status: str | None


CURRENT_ASSIGNMENT = and_(
    CustomerAssignment.member_id == Member.id, CustomerAssignment.is_current.is_(True),
)


def member_view(member: Member, settings: AuthSettings) -> MemberView:
    return MemberView.from_member(member, read_masked_phone(member.phone_ciphertext, settings))


def customer_view(
    member: Member, state: CustomerStatus, current_staff_id: UUID | None, settings: AuthSettings,
) -> CustomerView:
    return CustomerView(
        **member_view(member, settings).model_dump(),
        visit_status=state.visit_status, consume_status=state.consume_status, deal_status=state.deal_status,
        last_effective_contact_at=state.last_effective_contact_at.astimezone(UTC) if state.last_effective_contact_at else None,
        next_recall_at=state.next_recall_at.astimezone(UTC) if state.next_recall_at else None,
        current_staff_id=current_staff_id,
    )


def member_search(query: str, settings: AuthSettings) -> ColumnElement[bool]:
    text_match = or_(
        Member.name.icontains(query, autoescape=True),
        Member.member_no.icontains(query, autoescape=True),
    )
    if re.fullmatch(r"1[3-9][0-9]{9}", query):
        return Member.phone_search_hash == phone_search_digest(query, settings)
    return text_match


def count_rows(db: Session, query: Select[*tuple[Any, ...]]) -> int:
    return db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0


def customers() -> Select[Member, CustomerStatus, UUID]:
    return (
        select(Member, CustomerStatus, CustomerAssignment.staff_id)
        .join(CustomerStatus, CustomerStatus.member_id == Member.id)
        .outerjoin(CustomerAssignment, CURRENT_ASSIGNMENT)
    )


def customer_detail(db: Session, member_id: UUID, scope: ColumnElement[bool], settings: AuthSettings) -> CustomerView:
    row = db.execute(customers().where(Member.id == member_id, scope)).one_or_none()
    if row is None:
        raise APIError(404, "NOT_FOUND", "客户不存在")
    member, state, staff_id = row
    return customer_view(member, state, staff_id, settings)


def admin_member_detail(db: Session, member_id: UUID, settings: AuthSettings) -> AdminMemberView:
    source = aliased(StaffProfile)
    current = aliased(StaffProfile)
    row = db.execute(
        select(Member, CustomerStatus, source.display_name, current.display_name, CustomerAssignment.staff_id)
        .outerjoin(CustomerStatus, CustomerStatus.member_id == Member.id)
        .outerjoin(CustomerAssignment, CURRENT_ASSIGNMENT)
        .outerjoin(source, source.id == Member.source_employee_id)
        .outerjoin(current, current.id == CustomerAssignment.staff_id)
        .where(Member.id == member_id),
    ).one_or_none()
    if row is None:
        raise APIError(404, "NOT_FOUND", "会员不存在")
    member, state, source_name, current_name, current_staff_id = row
    return AdminMemberView(
        **member_view(member, settings).model_dump(),
        source_employee_id=member.source_employee_id, source_employee_name=source_name,
        current_staff_id=current_staff_id, current_staff_name=current_name,
        visit_status=state.visit_status if state else None, consume_status=state.consume_status if state else None,
        deal_status=state.deal_status if state else None,
    )
