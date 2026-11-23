from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import or_, select
from starlette.responses import JSONResponse

from app.auth.member import MemberView
from app.auth.routes import Authenticated, Database, MemberSession, Settings, require_permission
from app.auth.scopes import current_customer_assignment, customer_scope, own_customer_scope, owned_order
from app.db.models import CustomerStatus, Member, StaffProfile
from app.directory import (
    AdminMemberView, CustomerView, Page, StaffView, admin_member_detail, count_rows, customer_detail, customer_view,
    customers, member_search, member_view,
)
from app.http import APIError, SuccessEnvelope, success

router = APIRouter(prefix="/api/v1")
CustomerSession = Annotated[Authenticated, Depends(require_permission("R6"))]
AdminMemberSession = Annotated[Authenticated, Depends(require_permission("R11"))]
AdminStaffSession = Annotated[Authenticated, Depends(require_permission("R12"))]
PageNumber = Annotated[int, Query(ge=1, le=2147483647)]
PageSize = Annotated[int, Query(ge=1, le=100)]
SearchText = Annotated[str, Query(max_length=80)]
ProfileStatus = Literal["active", "disabled"]


class OrderView(BaseModel):
    id: UUID
    order_no: str
    product_id: UUID
    product_snapshot: dict[str, Any]
    quantity: int
    points_cost_total: str
    status: str
    created_at: datetime
    verified_at: datetime | None


@router.get("/customers/{id}", tags=["customers"], response_model=SuccessEnvelope[CustomerView])
def read_customer(
    request: Request, id: UUID, db: Database, session: CustomerSession, settings: Settings,
) -> JSONResponse:
    return success(request, customer_detail(db, id, customer_scope(session.identity), settings))


@router.get("/staff/me/customers", tags=["customers"], response_model=SuccessEnvelope[Page[CustomerView]])
def list_staff_customers(
    request: Request, db: Database, session: CustomerSession, settings: Settings,
    page: PageNumber = 1, page_size: PageSize = 20, q: SearchText = "",
    visit_status: Literal["not_visited", "visited"] | None = None,
    consume_status: Literal["not_consumed", "consumed"] | None = None,
    deal_status: Literal["not_dealt", "dealt"] | None = None,
) -> JSONResponse:
    query = customers().where(own_customer_scope(session.identity))
    if keyword := q.strip():
        query = query.where(member_search(keyword, settings))
    for column, value in (
        (CustomerStatus.visit_status, visit_status), (CustomerStatus.consume_status, consume_status),
        (CustomerStatus.deal_status, deal_status),
    ):
        if value is not None:
            query = query.where(column == value)
    total = count_rows(db, query)
    rows = db.execute(query.order_by(Member.registered_at.desc(), Member.id.desc()).offset((page - 1) * page_size).limit(page_size))
    items = [customer_view(member, state, staff_id, settings) for member, state, staff_id in rows]
    return success(request, Page[CustomerView](items=items, page=page, page_size=page_size, total=total))


@router.get("/admin/members", tags=["admin"], response_model=SuccessEnvelope[Page[MemberView]])
def list_admin_members(
    request: Request, db: Database, session: AdminMemberSession, settings: Settings,
    page: PageNumber = 1, page_size: PageSize = 20, q: SearchText = "",
    status: ProfileStatus | None = None, staff_id: UUID | None = None,
) -> JSONResponse:
    query = select(Member)
    if keyword := q.strip():
        query = query.where(member_search(keyword, settings))
    if status is not None:
        query = query.where(Member.status == status)
    if staff_id is not None:
        query = query.where(current_customer_assignment(staff_id))
    total = count_rows(db, query)
    rows = db.scalars(query.order_by(Member.registered_at.desc(), Member.id.desc()).offset((page - 1) * page_size).limit(page_size))
    items = [member_view(member, settings) for member in rows]
    return success(request, Page[MemberView](items=items, page=page, page_size=page_size, total=total))


@router.get("/admin/members/{id}", tags=["admin"], response_model=SuccessEnvelope[AdminMemberView])
def read_admin_member(request: Request, id: UUID, db: Database, session: AdminMemberSession, settings: Settings) -> JSONResponse:
    return success(request, admin_member_detail(db, id, settings))


@router.get("/admin/staff", tags=["admin"], response_model=SuccessEnvelope[Page[StaffView]])
def list_admin_staff(
    request: Request, db: Database, session: AdminStaffSession,
    page: PageNumber = 1, page_size: PageSize = 20, q: SearchText = "",
    role: Literal["employee", "manager", "admin"] | None = None, status: ProfileStatus | None = None,
) -> JSONResponse:
    query = select(StaffProfile)
    if keyword := q.strip():
        query = query.where(or_(
            StaffProfile.display_name.icontains(keyword, autoescape=True),
            StaffProfile.employee_no.icontains(keyword, autoescape=True),
        ))
    if role is not None:
        query = query.where(StaffProfile.role == role)
    if status is not None:
        query = query.where(StaffProfile.status == status)
    total = count_rows(db, query)
    rows = db.scalars(query.order_by(StaffProfile.created_at.desc(), StaffProfile.id.desc()).offset((page - 1) * page_size).limit(page_size))
    items = [StaffView.model_validate(staff) for staff in rows]
    return success(request, Page[StaffView](items=items, page=page, page_size=page_size, total=total))


@router.get("/admin/staff/{id}", tags=["admin"], response_model=SuccessEnvelope[StaffView])
def read_admin_staff(request: Request, id: UUID, db: Database, session: AdminStaffSession) -> JSONResponse:
    staff = db.get(StaffProfile, id)
    if staff is None:
        raise APIError(404, "NOT_FOUND", "员工档案不存在")
    return success(request, StaffView.model_validate(staff))


@router.get("/exchange-orders/{id}", tags=["exchange-orders"], response_model=SuccessEnvelope[OrderView])
def order_detail(request: Request, id: UUID, db: Database, session: MemberSession) -> JSONResponse:
    order = owned_order(db, session.identity, id)
    return success(request, OrderView(
        id=order.id, order_no=order.order_no, product_id=order.product_id,
        product_snapshot=order.product_snapshot, quantity=order.quantity,
        points_cost_total=str(order.points_cost_total), status=order.status, created_at=order.created_at.astimezone(UTC),
        verified_at=order.verified_at.astimezone(UTC) if order.verified_at else None,
    ))
