from typing import Literal

from sqlalchemy.orm import Session

from app.auth.identity import Identity
from app.db.models import OperationLog

AuthAction = Literal["refresh", "logout"]
AuthOutcome = Literal["success", "invalid_session", "identity_rejected", "refresh_replay"]


def write_auth_audit(
    db: Session,
    request_id: str,
    action: AuthAction,
    outcome: AuthOutcome,
    identity: Identity | None = None,
) -> None:
    db.add(OperationLog(
        actor_account_id=identity.account_id if identity else None,
        actor_role=(identity.selected_role or "registration") if identity else "anonymous",
        action=action,
        module="auth",
        summary=outcome,
        request_id=request_id,
    ))
    db.commit()
