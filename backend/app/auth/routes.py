from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from app.auth.audit import AuthAction, AuthOutcome, write_auth_audit
from app.auth.identity import Identity, resolve_identity
from app.auth.sessions import RejectedSession, SessionReference, SessionService, unavailable
from app.db.session import get_db
from app.http import SuccessEnvelope, success

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)
Database = Annotated[Session, Depends(get_db)]


def get_sessions(request: Request) -> SessionService:
    if not hasattr(request.app.state, "auth_sessions"):
        raise unavailable()
    return request.app.state.auth_sessions


Sessions = Annotated[SessionService, Depends(get_sessions)]


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: SecretStr = Field(max_length=256)


class SessionPayload(Identity):
    access_token: str
    refresh_token: str
    expires_in: int


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
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
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


def audit(
    db: Session, request: Request, action: AuthAction, outcome: AuthOutcome, identity: Identity | None = None
) -> None:
    try:
        write_auth_audit(db, request.state.request_id, action, outcome, identity)
    except SQLAlchemyError:
        raise unavailable() from None


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
    payload = SessionPayload(
        **identity.model_dump(), access_token=pair.access_token,
        refresh_token=pair.refresh_token, expires_in=pair.expires_in,
    )
    return success(request, payload)


@router.post("/logout", response_model=SuccessEnvelope[LogoutResult])
def logout(request: Request, service: Sessions, db: Database, session: CurrentSession) -> JSONResponse:
    service.revoke(session.reference)
    audit(db, request, "logout", "success", session.identity)
    return success(request, LogoutResult(logged_out=True))


@router.get("/me", response_model=SuccessEnvelope[Identity])
def me(request: Request, session: CurrentSession) -> JSONResponse:
    return success(request, session.identity)
