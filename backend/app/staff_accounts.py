import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.identity import Identity, resolve_identity
from app.auth.sessions import KEY_PREFIX, SessionService, TokenPair, unavailable
from app.db.models import Account, Member, OperationLog, StaffProfile
from app.directory import StaffView
from app.http import APIError

INVITE_SECONDS = 600
INVITE_PREFIX = "sunshine-staff-bind:v1:"
CONSUME_INVITE = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
return redis.call('DEL', KEYS[1])
"""


class StaffCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_no: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32, pattern=r"^[^\x00]+$")]
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80, pattern=r"^[^\x00]+$")]


class StaffStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["active", "disabled"]


class AdminStaffView(StaffView):
    wechat_bound: bool

    @classmethod
    def of(cls, staff: StaffProfile, account: Account) -> "AdminStaffView":
        return cls(**StaffView.model_validate(staff).model_dump(), wechat_bound=bool(account.wechat_openid))


class BindingInvitation(BaseModel):
    qr_payload: str
    expires_at: datetime


def _invite_key(staff_id: UUID) -> str:
    return f"{KEY_PREFIX}:staff-binding:{staff_id}"


def _invite_digest(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _invalid_invite() -> APIError:
    return APIError(409, "STAFF_INVITATION_INVALID", "员工绑定邀请无效、已过期或已使用")


def _binding_conflict() -> APIError:
    return APIError(409, "STAFF_BINDING_CONFLICT", "微信或员工档案已关联其他身份，请联系管理员")


def _staff_for_update(db: Session, staff_id: UUID) -> tuple[StaffProfile, Account]:
    staff = db.scalar(select(StaffProfile).where(StaffProfile.id == staff_id).with_for_update())
    if staff is None:
        raise APIError(404, "NOT_FOUND", "员工档案不存在")
    if staff.role != "employee":
        raise APIError(403, "FORBIDDEN", "只能管理普通员工")
    account = db.scalars(select(Account).where(Account.id == staff.account_id).with_for_update()).one()
    return staff, account


def _eligible(staff: StaffProfile, account: Account) -> bool:
    return account.status == "active" and staff.status == "active" and staff.disabled_at is None


def _audit(db: Session, action: str, staff_id: UUID, actor: Identity, request_id: str,
           after: dict[str, str | bool], before: dict[str, str | bool] | None = None) -> None:
    assert actor.selected_role in ("admin", "employee")
    db.add(OperationLog(
        actor_account_id=actor.account_id, actor_role=actor.selected_role, action=action, module="staff",
        target_type="staff", target_id=staff_id, request_id=request_id, before_data=before, after_data=after,
    ))


def create_staff(db: Session, body: StaffCreate, actor: Identity, request_id: str) -> AdminStaffView:
    account = Account(status="active")
    db.add(account)
    db.flush()
    staff = StaffProfile(account_id=account.id, role="employee", status="active", **body.model_dump())
    db.add(staff)
    try:
        db.flush()
    except IntegrityError as exc:
        if getattr(getattr(exc.orig, "diag", None), "constraint_name", None) == "staff_profiles_employee_no_key":
            raise APIError(409, "EMPLOYEE_NO_EXISTS", "员工工号已存在") from None
        raise
    result = AdminStaffView.of(staff, account)
    _audit(db, "staff_create", staff.id, actor, request_id, {"status": staff.status, "role": staff.role})
    db.commit()
    return result


def issue_invitation(db: Session, sessions: SessionService, staff_id: UUID, actor: Identity,
                     request_id: str) -> BindingInvitation:
    staff, account = _staff_for_update(db, staff_id)
    if account.wechat_openid or not _eligible(staff, account):
        raise APIError(409, "STAFF_INVITATION_NOT_AVAILABLE", "仅可为未绑定且在职的员工签发邀请")
    payload = f"{INVITE_PREFIX}{staff_id}.{secrets.token_urlsafe(32)}"
    expires = datetime.now(UTC) + timedelta(seconds=INVITE_SECONDS)
    try:
        sessions.cache.set(_invite_key(staff_id), _invite_digest(payload), ex=INVITE_SECONDS)
    except RedisError:
        raise unavailable() from None
    _audit(db, "staff_invite", staff_id, actor, request_id, {"expires_at": expires.isoformat()})
    db.commit()
    return BindingInvitation(qr_payload=payload, expires_at=expires)


def invitation_target(sessions: SessionService, payload: str) -> UUID:
    match = re.fullmatch(re.escape(INVITE_PREFIX) + r"([0-9a-f-]{36})\.[A-Za-z0-9_-]{43}", payload)
    if match:
        try:
            staff_id = UUID(match[1])
        except ValueError:
            pass
        else:
            try:
                if sessions.cache.get(_invite_key(staff_id)) == _invite_digest(payload):
                    return staff_id
            except RedisError:
                raise unavailable() from None
    raise _invalid_invite()


def bind_employee(db: Session, sessions: SessionService, staff_id: UUID, payload: str,
                  openid: str, request_id: str) -> None:
    # Issuance and consumption share the staff row lock. Compare-and-delete also enforces the Redis TTL.
    staff, placeholder = _staff_for_update(db, staff_id)
    try:
        if sessions.cache.get(_invite_key(staff_id)) != _invite_digest(payload):
            raise _invalid_invite()
        if not _eligible(staff, placeholder) or any(
            (placeholder.wechat_openid, placeholder.wechat_unionid, placeholder.username, placeholder.password_hash)
        ) or db.scalar(select(Member.id).where(Member.account_id == placeholder.id)) is not None:
            raise _binding_conflict()
        existing = db.scalar(select(Account).where(Account.wechat_openid == openid).with_for_update())
        if existing is not None and (
            existing.status != "active" or existing.username or existing.password_hash
            or db.scalar(select(StaffProfile.id).where(StaffProfile.account_id == existing.id)) is not None
        ):
            raise _binding_conflict()
        if sessions.cache.eval(CONSUME_INVITE, 1, _invite_key(staff_id), _invite_digest(payload)) != 1:
            raise _invalid_invite()
    except RedisError:
        raise unavailable() from None
    now = datetime.now(UTC)
    if existing is None:
        placeholder.wechat_openid = openid
        placeholder.updated_at = now
        bound_account = placeholder
    else:
        staff.account_id = existing.id
        placeholder.status = "disabled"
        placeholder.updated_at = now
        bound_account = existing
    staff.updated_at = now
    try:
        db.flush()
    except IntegrityError as exc:
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if constraint in ("accounts_wechat_openid_key", "staff_profiles_account_id_key"):
            raise _binding_conflict() from None
        raise
    identity = Identity(
        account_id=bound_account.id, selected_role="employee", available_roles=["employee"], registration_required=False,
    )
    _audit(db, "staff_bind", staff_id, identity, request_id, {"wechat_bound": True})
    db.commit()


def employee_login(db: Session, sessions: SessionService, openid: str) -> tuple[Identity, TokenPair]:
    # Serialize issuance against staff status changes.
    account_id = db.scalar(select(StaffProfile.account_id).join(Account, Account.id == StaffProfile.account_id)
                           .where(Account.wechat_openid == openid, StaffProfile.role == "employee")
                           .with_for_update(read=True, of=StaffProfile))
    identity = resolve_identity(db, account_id, "employee", "miniprogram") if account_id is not None else None
    if identity is None:
        raise APIError(403, "EMPLOYEE_ACCOUNT_UNAVAILABLE", "员工身份未绑定或不可用，请联系管理员")
    return identity, sessions.issue(identity.account_id, "employee", "miniprogram")


def set_staff_status(db: Session, sessions: SessionService, staff_id: UUID, status: str, actor: Identity,
                     request_id: str) -> AdminStaffView:
    staff, account = _staff_for_update(db, staff_id)
    active = status == "active"
    if staff.status != status or (staff.disabled_at is None) != active:
        sessions.revoke_employee(account.id)
        try:
            sessions.cache.delete(_invite_key(staff_id))
        except RedisError:
            raise unavailable() from None
        before = staff.status
        now = datetime.now(UTC)
        staff.status = status
        staff.disabled_at = None if active else now
        staff.updated_at = now
        _audit(db, "staff_enable" if active else "staff_disable", staff.id, actor, request_id,
               {"status": status}, {"status": before})
    result = AdminStaffView.of(staff, account)
    db.commit()
    return result
