from hashlib import sha256
from typing import Final

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.audit import AuthOutcome
from app.auth.identity import Identity, resolve_identity
from app.auth.passwords import verify_password
from app.auth.sessions import KEY_PREFIX, unavailable
from app.db.models import Account, StaffProfile

CHANNEL: Final = "admin_web"
WINDOW_SECONDS = 300
SOURCE_LIMIT = 30
PAIR_LIMIT = 5

# Check both buckets and consume the attempt atomically, including their initial expiry.
TAKE_ATTEMPT = """
local retry_after = 0
for i, key in ipairs(KEYS) do
    if tonumber(redis.call('GET', key) or '0') >= tonumber(ARGV[i]) then
        retry_after = math.max(retry_after, redis.call('TTL', key), 1)
    end
end
if retry_after > 0 then
    return retry_after
end
for _, key in ipairs(KEYS) do
    if redis.call('INCR', key) == 1 then
        redis.call('EXPIRE', key, tonumber(ARGV[3]))
    end
end
return 0
"""


def login_retry_after(cache: Redis, source: str, username: str) -> int:
    source_digest = sha256(source.encode()).hexdigest()
    pair_digest = sha256(f"{source_digest}:{username.casefold()}".encode()).hexdigest()
    try:
        result = cache.eval(
            TAKE_ATTEMPT, 2, f"{KEY_PREFIX}:admin-login:source:{source_digest}",
            f"{KEY_PREFIX}:admin-login:pair:{pair_digest}", str(SOURCE_LIMIT), str(PAIR_LIMIT), str(WINDOW_SECONDS),
        )
    except RedisError:
        raise unavailable() from None
    if not isinstance(result, int):
        raise unavailable()
    return result


def check_credentials(db: Session, username: str, password: str) -> tuple[Identity | None, AuthOutcome]:
    try:
        candidate = db.execute(
            select(Account.id, Account.password_hash, Account.status, StaffProfile.id, StaffProfile.role)
            .select_from(Account)
            .outerjoin(StaffProfile, StaffProfile.account_id == Account.id)
            .where(Account.username == username)
        ).one_or_none()
        valid_password = verify_password(password, candidate.password_hash if candidate else None)
        if candidate is None:
            return None, "unknown_account"
        account_id, _, status, staff_id, role = candidate
        if not valid_password:
            return None, "invalid_password"
        if status != "active":
            return None, "inactive_account"
        if staff_id is None:
            return None, "missing_staff_profile"
        if role != "manager" and role != "admin":
            return None, "invalid_staff_role"
        identity = resolve_identity(db, account_id, "admin" if role == "admin" else "manager", CHANNEL)
        return (identity, "success") if identity else (None, "identity_rejected")
    except SQLAlchemyError:
        raise unavailable() from None
