from typing import Literal

from sqlalchemy.orm import Session

from app.auth.identity import Channel, Identity
from app.db.models import OperationLog

AuthAction = Literal["refresh", "logout", "admin_login"]
AuthOutcome = Literal[
    "success", "invalid_session", "identity_rejected", "refresh_replay", "rate_limited",
    "unknown_account", "invalid_password", "inactive_account", "missing_staff_profile",
    "invalid_staff_role", "dependency_unavailable",
]


def write_auth_audit(
    db: Session,
    request_id: str,
    action: AuthAction,
    outcome: AuthOutcome,
    identity: Identity | None = None,
    *,
    channel: Channel | None = None,
) -> None:
    db.add(OperationLog(
        actor_account_id=identity.account_id if identity else None,
        actor_role=(identity.selected_role or "registration") if identity else "anonymous",
        action=action,
        module="auth",
        summary=outcome,
        after_data={"channel": channel} if channel else None,
        request_id=request_id,
    ))
    db.commit()
