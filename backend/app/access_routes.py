from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import and_, select
from starlette.responses import JSONResponse

from app.auth.member import MemberView
from app.auth.phone import read_masked_phone
from app.auth.routes import Authenticated, Database, MemberSession, Settings, require_permission
from app.auth.scopes import customer_scope, owned_order
from app.db.models import CustomerAssignment, CustomerStatus, Member
from app.http import APIError, SuccessEnvelope, success

router = APIRouter(prefix="/api/v1")
CustomerSession = Annotated[Authenticated, Depends(require_permission("R6"))]


class CustomerView(MemberView):
    visit_status: str
    consume_status: str
    deal_status: str
    last_effective_contact_at: datetime | None
    next_recall_at: datetime | None
    current_staff_id: UUID | None


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
def customer_detail(
    request: Request, id: UUID, db: Database, session: CustomerSession, settings: Settings,
) -> JSONResponse:
    row = db.execute(
        select(Member, CustomerStatus, CustomerAssignment.staff_id)
        .join(CustomerStatus, CustomerStatus.member_id == Member.id)
        .outerjoin(CustomerAssignment, and_(
            CustomerAssignment.member_id == Member.id, CustomerAssignment.is_current.is_(True),
        ))
        .where(Member.id == id, customer_scope(session.identity)),
    ).one_or_none()
    if row is None:
        raise APIError(404, "NOT_FOUND", "客户不存在")
    member, state, current_staff_id = row
    profile = MemberView.from_member(member, read_masked_phone(member.phone_ciphertext, settings))
    return success(request, CustomerView(
        **profile.model_dump(),
        visit_status=state.visit_status, consume_status=state.consume_status, deal_status=state.deal_status,
        last_effective_contact_at=state.last_effective_contact_at.astimezone(UTC) if state.last_effective_contact_at else None,
        next_recall_at=state.next_recall_at.astimezone(UTC) if state.next_recall_at else None,
        current_staff_id=current_staff_id,
    ))


@router.get("/exchange-orders/{id}", tags=["exchange-orders"], response_model=SuccessEnvelope[OrderView])
def order_detail(request: Request, id: UUID, db: Database, session: MemberSession) -> JSONResponse:
    order = owned_order(db, session.identity, id)
    return success(request, OrderView(
        id=order.id, order_no=order.order_no, product_id=order.product_id,
        product_snapshot=order.product_snapshot, quantity=order.quantity,
        points_cost_total=str(order.points_cost_total), status=order.status, created_at=order.created_at.astimezone(UTC),
        verified_at=order.verified_at.astimezone(UTC) if order.verified_at else None,
    ))
