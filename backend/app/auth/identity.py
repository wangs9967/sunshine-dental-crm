from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Account, Member, StaffProfile

Role = Literal["member", "employee", "manager", "admin"]
Channel = Literal["miniprogram", "admin_web"]


class Identity(BaseModel):
    account_id: UUID
    selected_role: Role | None
    available_roles: list[Role]
    registration_required: bool


def resolve_identity(
    db: Session, account_id: UUID, selected_role: Role | None, channel: Channel
) -> Identity | None:
    result = db.execute(
        select(
            Account.status, Account.wechat_openid != "", Member.id, Member.status,
            StaffProfile.status, StaffProfile.role, StaffProfile.disabled_at,
        )
        .select_from(Account)
        .outerjoin(Member, Member.account_id == Account.id)
        .outerjoin(StaffProfile, StaffProfile.account_id == Account.id)
        .where(Account.id == account_id)
    ).one_or_none()
    if result is None:
        return None
    account_status, wechat_linked, member_id, member_status, staff_status, staff_role, staff_disabled_at = result
    if account_status != "active":
        return None

    available_roles: list[Role] = []
    registration_required = False
    if channel == "miniprogram" and wechat_linked:
        if selected_role == "employee":
            # Validate already-issued employee sessions without exposing employee login or switching.
            if staff_role == "employee" and staff_status == "active" and staff_disabled_at is None:
                available_roles.append("employee")
        else:
            registration_required = member_id is None
            if member_status == "active":
                available_roles.append("member")
    elif channel == "admin_web" and staff_status == "active" and staff_disabled_at is None:
        if staff_role == "manager":
            available_roles.append("manager")
        elif staff_role == "admin":
            available_roles.append("admin")

    if selected_role is None:
        if not registration_required:
            return None
    elif selected_role not in available_roles:
        return None

    return Identity(
        account_id=account_id,
        selected_role=selected_role,
        available_roles=available_roles,
        registration_required=registration_required,
    )
