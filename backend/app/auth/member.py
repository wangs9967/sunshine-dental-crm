import hashlib
import re
from datetime import UTC, date, datetime
from typing import Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.auth.identity import Identity, Role, resolve_identity
from app.auth.permissions import check_permission
from app.auth.phone import mask_phone, protect_phone, read_masked_phone
from app.config import AuthSettings
from app.db.models import (
    Account, CustomerAssignment, CustomerStatus, EmployeeQrToken, Member, OperationLog, PointsAccount, StaffProfile,
)
from app.http import APIError

SourceStatus = Literal["none", "bound", "invalid"]
BUSINESS_ZONE = ZoneInfo("Asia/Shanghai")


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=80, pattern=r"^[^\x00-\x1f\x7f]+$")
    birthday: date
    phone: SecretStr
    scene_token: SecretStr | None = Field(default=None, max_length=256)

    @field_validator("birthday", mode="before")
    @classmethod
    def validate_birthday(cls, value: object) -> date:
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ValueError("Use YYYY-MM-DD")
        birthday = date.fromisoformat(value)
        if birthday > datetime.now(BUSINESS_ZONE).date():
            raise ValueError("Birthday must not be in the future")
        return birthday

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: SecretStr) -> SecretStr:
        phone = value.get_secret_value().strip()
        if not re.fullmatch(r"1[3-9][0-9]{9}", phone):
            raise ValueError("Use an 11-digit mainland mobile number")
        return SecretStr(phone)


class MemberView(BaseModel):
    id: UUID
    member_no: str
    name: str
    birthday: date
    phone_masked: str
    status: str
    registered_at: datetime

    @classmethod
    def from_member(cls, member: Member, phone_masked: str) -> "MemberView":
        return cls(
            id=member.id, member_no=member.member_no, name=member.name, birthday=member.birthday,
            phone_masked=phone_masked, status=member.status, registered_at=member.registered_at.astimezone(UTC),
        )


def read_member(db: Session, account_id: UUID, settings: AuthSettings) -> MemberView:
    member = db.scalar(select(Member).where(Member.account_id == account_id, Member.status == "active"))
    if member is None:
        raise APIError(404, "NOT_FOUND", "会员资料不存在")
    return MemberView.from_member(member, read_masked_phone(member.phone_ciphertext, settings))


def login_identity(db: Session, openid: str) -> Identity:
    db.execute(insert(Account).values(wechat_openid=openid).on_conflict_do_nothing(
        index_elements=[Account.wechat_openid],
    ))
    account_id = db.scalars(select(Account.id).where(Account.wechat_openid == openid)).one()
    exists = db.scalar(select(Member.id).where(Member.account_id == account_id)) is not None
    identity = resolve_identity(db, account_id, "member" if exists else None, "miniprogram")
    if identity is None:
        raise APIError(403, "MEMBER_ACCOUNT_UNAVAILABLE", "当前会员账号不可用，请联系门诊")
    return identity


def _source_employee(db: Session, token: str) -> UUID | None:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", token):
        return None
    return db.scalar(
        select(EmployeeQrToken.staff_id)
        .join(StaffProfile, StaffProfile.id == EmployeeQrToken.staff_id)
        .join(Account, Account.id == StaffProfile.account_id)
        .where(
            EmployeeQrToken.token_hash == hashlib.sha256(token.encode("ascii")).digest(),
            EmployeeQrToken.revoked_at.is_(None),
            EmployeeQrToken.expires_at > datetime.now(UTC),
            StaffProfile.status == "active", StaffProfile.disabled_at.is_(None),
            StaffProfile.role.in_(["employee", "manager", "admin"]),
            Account.status == "active",
        )
        .with_for_update(read=True, of=(EmployeeQrToken, StaffProfile)),
    )


def register_member(
    db: Session, account_id: UUID, selected_role: Role | None, body: RegisterRequest,
    settings: AuthSettings, request_id: str,
) -> tuple[MemberView, SourceStatus]:
    account = db.scalars(select(Account).where(Account.id == account_id).with_for_update()).one_or_none()
    if account is None or account.status != "active" or not account.wechat_openid:
        raise APIError(403, "MEMBER_ACCOUNT_UNAVAILABLE", "当前会员账号不可用，请联系门诊")
    if db.scalar(select(Member.id).where(Member.account_id == account_id)) is not None:
        raise APIError(409, "MEMBER_ALREADY_REGISTERED", "会员已注册，请重新微信登录")
    check_permission("R1", selected_role)

    phone = body.phone.get_secret_value()
    ciphertext, search_hash = protect_phone(phone, settings)
    scene = body.scene_token.get_secret_value() if body.scene_token is not None else None
    staff_id = _source_employee(db, scene) if scene is not None else None
    source: SourceStatus = "bound" if staff_id else ("invalid" if scene is not None else "none")
    member = Member(
        account_id=account_id, member_no=uuid4().hex, name=body.name, birthday=body.birthday,
        phone_ciphertext=ciphertext, phone_search_hash=search_hash,
        register_source="employee_qr" if staff_id else "direct", source_employee_id=staff_id,
    )
    db.add(member)
    db.flush()
    db.add_all([
        CustomerStatus(member_id=member.id),
        PointsAccount(member_id=member.id),
        OperationLog(
            actor_account_id=account_id, actor_role="member", action="member_register", module="auth",
            target_type="member", target_id=member.id, summary="success", request_id=request_id,
            after_data={"channel": "miniprogram", "source_status": source},
        ),
    ])
    if staff_id:
        db.add(CustomerAssignment(
            member_id=member.id, staff_id=staff_id, bind_source="employee_qr", operator_account_id=account_id,
        ))
    db.flush()
    return MemberView.from_member(member, mask_phone(phone)), source
