from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from app.auth.admin_login import CHANNEL, check_credentials, login_retry_after
from app.auth.audit import AuthAction, AuthOutcome, write_auth_audit
from app.auth.identity import Channel, Identity, resolve_identity
from app.auth.member import MemberView, RegisterRequest, SourceStatus, login_identity, read_member, register_member
from app.auth.permissions import Permission, check_permission
from app.auth.sessions import RejectedSession, SessionReference, SessionService, TokenPair, unavailable
from app.auth.wechat import exchange_code
from app.config import AuthSettings
from app.db.models import Member, OperationLog, PointsAccount
from app.db.session import get_db
from app.http import APIError, SuccessEnvelope, error, success
from app.staff_accounts import bind_employee, employee_login, invitation_target

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
members_router = APIRouter(prefix="/api/v1/members", tags=["members"])
bearer = HTTPBearer(auto_error=False)
Database = Annotated[Session, Depends(get_db)]
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def get_sessions(request: Request) -> SessionService:
    if not hasattr(request.app.state, "auth_sessions"):
        raise unavailable()
    return request.app.state.auth_sessions


Sessions = Annotated[SessionService, Depends(get_sessions)]


def auth_settings(request: Request) -> AuthSettings:
    return request.app.state.auth_settings


Settings = Annotated[AuthSettings, Depends(auth_settings)]


class WechatLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: SecretStr = Field(min_length=1, max_length=256)
    scene_token: SecretStr | None = Field(default=None, max_length=256)
    role: Literal["member", "employee"] = "member"


class StaffBindRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: SecretStr = Field(min_length=1, max_length=256)
    invitation: SecretStr = Field(min_length=1, max_length=128)


class StaffBindResult(BaseModel):
    wechat_bound: bool = True


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: SecretStr = Field(max_length=256)


class AdminLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=64, pattern=r"^[^\x00]+$")
    password: SecretStr = Field(min_length=1, max_length=256)


class SessionPayload(Identity):
    access_token: str
    refresh_token: str
    expires_in: int


class RegistrationPayload(MemberView):
    source_status: SourceStatus
    session: SessionPayload


class PointsView(BaseModel):
    member_id: str
    balance: str
    total_earned: str
    total_spent: str


class LogoutResult(BaseModel):
    logged_out: bool


@dataclass(frozen=True)
class Authenticated:
    reference: SessionReference
    identity: Identity


def current_identity(db: Session, reference: SessionReference) -> Identity | None:
    record = reference.record
    try:
        return resolve_identity(db, record.account_id, record.selected_role, record.channel)
    except SQLAlchemyError:
        raise unavailable() from None


def authenticate(
    session_service: Sessions,
    db: Database,
    credentials: Credentials,
) -> Authenticated:
    if credentials is None:
        raise RejectedSession()
    reference = session_service.access(credentials.credentials)
    identity = current_identity(db, reference)
    if identity is None:
        raise RejectedSession()
    # Confirm that a concurrent logout or rotation did not invalidate the session during the DB read.
    return Authenticated(session_service.access(credentials.credentials), identity)


CurrentSession = Annotated[Authenticated, Depends(authenticate)]


def require_permission(permission: Permission) -> Callable[..., Authenticated]:
    def check(request: Request, db: Database, session: CurrentSession) -> Authenticated:
        try:
            check_permission(permission, session.identity.selected_role)
        except APIError as exc:
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                db.add(OperationLog(
                    actor_account_id=session.identity.account_id,
                    actor_role=session.identity.selected_role or "registration",
                    action="permission_denied",
                    module="auth",
                    summary=exc.code,
                    after_data={"permission": permission, "channel": session.reference.record.channel},
                    request_id=request.state.request_id,
                ))
                db.commit()
            raise
        return session
    return check


MemberSession = Annotated[Authenticated, Depends(require_permission("R2"))]


def audit(
    db: Session, request: Request, action: AuthAction, outcome: AuthOutcome, identity: Identity | None = None,
    *, channel: Channel | None = None,
) -> None:
    try:
        write_auth_audit(db, request.state.request_id, action, outcome, identity, channel=channel)
    except SQLAlchemyError:
        raise unavailable() from None


def session_payload(identity: Identity, pair: TokenPair) -> SessionPayload:
    return SessionPayload(
        **identity.model_dump(), access_token=pair.access_token,
        refresh_token=pair.refresh_token, expires_in=pair.expires_in,
    )


@router.post("/wechat/login", response_model=SuccessEnvelope[SessionPayload])
def wechat_login(request: Request, body: WechatLoginRequest, service: Sessions, db: Database,
                 settings: Settings) -> JSONResponse:
    openid = exchange_code(body.code.get_secret_value(), settings)
    try:
        if body.role == "employee":
            identity, pair = employee_login(db, service, openid)
        else:
            identity = login_identity(db, openid)
            pair = service.issue(identity.account_id, identity.selected_role, "miniprogram")
    except SQLAlchemyError:
        raise unavailable() from None
    audit(db, request, "wechat_login", "success", identity, channel="miniprogram")
    return success(request, session_payload(identity, pair))


@router.post("/wechat/staff-bind", response_model=SuccessEnvelope[StaffBindResult])
def staff_bind(request: Request, body: StaffBindRequest, service: Sessions, db: Database, settings: Settings) -> JSONResponse:
    invitation = body.invitation.get_secret_value()
    staff_id = invitation_target(service, invitation)
    openid = exchange_code(body.code.get_secret_value(), settings)
    bind_employee(db, service, staff_id, invitation, openid, request.state.request_id)
    return success(request, StaffBindResult())


@members_router.post("/register", status_code=201, response_model=SuccessEnvelope[RegistrationPayload])
def register(request: Request, body: RegisterRequest, credentials: Credentials, service: Sessions,
             db: Database, settings: Settings) -> JSONResponse:
    if credentials is None:
        raise RejectedSession()
    reference = service.access(credentials.credentials)
    record = reference.record
    if record.channel != "miniprogram" or record.selected_role not in (None, "member"):
        raise APIError(403, "FORBIDDEN", "当前身份不能注册会员")
    try:
        with db.begin():
            member, source = register_member(
                db, record.account_id, record.selected_role, body, settings, request.state.request_id,
            )
            service.access(credentials.credentials)
            identity = Identity(
                account_id=record.account_id, selected_role="member",
                available_roles=["member"], registration_required=False,
            )
            # Issue before commit. The new session is unusable while the member row is uncommitted.
            pair = service.issue(record.account_id, "member", "miniprogram")
    except SQLAlchemyError:
        raise APIError(503, "MEMBER_REGISTRATION_UNAVAILABLE", "注册暂不可用，请稍后重试") from None
    payload = RegistrationPayload(**member.model_dump(), source_status=source, session=session_payload(identity, pair))
    return success(request, payload, status=201)


@members_router.get("/me", response_model=SuccessEnvelope[MemberView])
def my_profile(request: Request, db: Database, session: MemberSession, settings: Settings) -> JSONResponse:
    return success(request, read_member(db, session.identity.account_id, settings))


@members_router.get("/me/points", response_model=SuccessEnvelope[PointsView])
def my_points(request: Request, db: Database, session: MemberSession) -> JSONResponse:
    points = db.scalar(select(PointsAccount).join(Member).where(Member.account_id == session.identity.account_id))
    if points is None:
        raise APIError(404, "NOT_FOUND", "积分账户不存在")
    return success(request, PointsView(
        member_id=str(points.member_id), balance=str(points.balance),
        total_earned=str(points.total_earned), total_spent=str(points.total_spent),
    ))


@router.post("/admin/login", response_model=SuccessEnvelope[SessionPayload])
def admin_login(request: Request, body: AdminLoginRequest, service: Sessions, db: Database) -> JSONResponse:
    try:
        retry_after = login_retry_after(service.cache, request.client.host if request.client else "", body.username)
        identity, outcome = (None, "rate_limited") if retry_after else check_credentials(
            db, body.username, body.password.get_secret_value(),
        )
        pair = service.issue(identity.account_id, identity.selected_role, CHANNEL) if identity else None
    except APIError:
        db.rollback()
        audit(db, request, "admin_login", "dependency_unavailable", channel=CHANNEL)
        raise
    audit(db, request, "admin_login", outcome, identity, channel=CHANNEL)
    if retry_after:
        return error(
            request, 429, "LOGIN_RATE_LIMITED", "登录尝试过于频繁，请稍后再试",
            headers={"Retry-After": str(retry_after)},
        )
    if identity is None or pair is None:
        return error(request, 401, "INVALID_CREDENTIALS", "用户名或密码错误")
    return success(request, session_payload(identity, pair))


@router.post("/refresh", response_model=SuccessEnvelope[SessionPayload])
def refresh_session(request: Request, body: RefreshRequest, service: Sessions, db: Database) -> JSONResponse:
    try:
        reference = service.refresh(body.refresh_token.get_secret_value())
        identity = current_identity(db, reference)
    except RejectedSession as exc:
        audit(db, request, "refresh", "refresh_replay" if exc.replay else "invalid_session")
        raise
    if identity is None:
        audit(db, request, "refresh", "identity_rejected")
        raise RejectedSession()
    try:
        pair = service.rotate(reference)
    except RejectedSession as exc:
        audit(db, request, "refresh", "refresh_replay" if exc.replay else "invalid_session", identity)
        raise
    audit(db, request, "refresh", "success", identity)
    return success(request, session_payload(identity, pair))


@router.post("/logout", response_model=SuccessEnvelope[LogoutResult])
def logout(request: Request, service: Sessions, db: Database, session: CurrentSession) -> JSONResponse:
    service.revoke(session.reference)
    audit(db, request, "logout", "success", session.identity)
    return success(request, LogoutResult(logged_out=True))


@router.get("/me", response_model=SuccessEnvelope[Identity])
def me(request: Request, session: CurrentSession) -> JSONResponse:
    return success(request, session.identity)
