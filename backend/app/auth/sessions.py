import hashlib
import re
import secrets
import time
from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ValidationError
from redis import Redis
from redis.exceptions import RedisError, WatchError

from app.auth.identity import Channel, Role
from app.config import AuthSettings
from app.http import APIError

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")
KEY_PREFIX = "sunshine:auth:v1"


class RejectedSession(APIError):
    def __init__(self, *, replay: bool = False) -> None:
        super().__init__(401, "INVALID_SESSION", "登录会话无效或已过期")
        self.replay = replay


def unavailable() -> APIError:
    return APIError(503, "AUTH_UNAVAILABLE", "认证服务暂时不可用")


def digest(token: str) -> str:
    if not TOKEN_PATTERN.fullmatch(token):
        raise RejectedSession()
    return hashlib.sha256(token.encode("ascii")).hexdigest()


class SessionRecord(BaseModel):
    account_id: UUID
    selected_role: Role | None
    channel: Channel
    issued_at: int
    access_expires_at: int
    expires_at: int
    revoked_at: int | None = None
    access_digest: str
    refresh_digest: str

    def active(self, now: int) -> bool:
        return self.revoked_at is None and self.expires_at > now


@dataclass(frozen=True)
class SessionReference:
    key: str
    token_digest: str
    record: SessionRecord


@dataclass(frozen=True, repr=False)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


class SessionService:
    def __init__(self, cache: Redis, settings: AuthSettings) -> None:
        self.cache = cache
        self.access_ttl = settings.auth_access_ttl_seconds
        self.session_ttl = settings.auth_session_ttl_seconds

    @staticmethod
    def _read(raw: object) -> SessionRecord:
        if raw is None:
            raise RejectedSession()
        if not isinstance(raw, str):
            raise unavailable()
        try:
            return SessionRecord.model_validate_json(raw)
        except ValidationError:
            raise unavailable() from None

    @staticmethod
    def _token_key(kind: str, token_digest: str) -> str:
        return f"{KEY_PREFIX}:{kind}:{token_digest}"

    @staticmethod
    def _tokens() -> tuple[str, str]:
        return secrets.token_urlsafe(32), secrets.token_urlsafe(32)

    def _reference(self, kind: str, token: str) -> SessionReference:
        token_digest = digest(token)
        try:
            key = self.cache.get(self._token_key(kind, token_digest))
            if key is None:
                raise RejectedSession()
            if not isinstance(key, str) or not key.startswith(f"{KEY_PREFIX}:session:"):
                raise unavailable()
            return SessionReference(key, token_digest, self._read(self.cache.get(key)))
        except RedisError:
            raise unavailable() from None

    def issue(self, account_id: UUID, selected_role: Role | None, channel: Channel) -> TokenPair:
        """Issue a session after a trusted login flow has verified the identity."""
        now = int(time.time())
        access, refresh = self._tokens()
        key = f"{KEY_PREFIX}:session:{uuid4()}"
        record = SessionRecord(
            account_id=account_id, selected_role=selected_role, channel=channel,
            issued_at=now, access_expires_at=now + self.access_ttl, expires_at=now + self.session_ttl,
            access_digest=digest(access), refresh_digest=digest(refresh),
        )
        try:
            with self.cache.pipeline() as pipe:
                pipe.set(key, record.model_dump_json(), exat=record.expires_at)
                pipe.set(self._token_key("access", record.access_digest), key, exat=record.access_expires_at)
                pipe.set(self._token_key("refresh", record.refresh_digest), key, exat=record.expires_at)
                pipe.execute()
        except RedisError:
            raise unavailable() from None
        return TokenPair(access, refresh, self.access_ttl)

    def access(self, token: str) -> SessionReference:
        reference = self._reference("access", token)
        now = int(time.time())
        if (
            not reference.record.active(now)
            or reference.record.access_expires_at <= now
            or reference.record.access_digest != reference.token_digest
        ):
            raise RejectedSession()
        return reference

    def refresh(self, token: str) -> SessionReference:
        reference = self._reference("refresh", token)
        if reference.record.refresh_digest != reference.token_digest:
            self._update(reference, "replay")
        if not reference.record.active(int(time.time())):
            raise RejectedSession()
        return reference

    def rotate(self, reference: SessionReference) -> TokenPair:
        access, refresh = self._tokens()
        expires_in = self._update(reference, "rotate", access, refresh)
        return TokenPair(access, refresh, expires_in)

    def revoke(self, reference: SessionReference) -> None:
        self._update(reference, "logout")

    def _update(
        self, reference: SessionReference, action: Literal["rotate", "replay", "logout"],
        access: str = "", refresh: str = "",
    ) -> int:
        try:
            for _ in range(5):
                with self.cache.pipeline() as pipe:
                    try:
                        pipe.watch(reference.key)
                        record = self._read(pipe.get(reference.key))
                        now = int(time.time())
                        replay = action != "logout" and record.refresh_digest != reference.token_digest
                        if not record.active(now) or (action == "replay" and not replay):
                            raise RejectedSession(replay=replay)
                        if action == "logout" and (
                            record.access_digest != reference.token_digest or record.access_expires_at <= now
                        ):
                            raise RejectedSession()

                        pipe.multi()
                        expires_in = 0
                        if replay or action == "logout":
                            record.revoked_at = now
                        else:
                            expires_in = min(self.access_ttl, record.expires_at - now)
                            record.access_digest = digest(access)
                            record.refresh_digest = digest(refresh)
                            record.access_expires_at = now + expires_in
                            pipe.set(
                                self._token_key("access", record.access_digest), reference.key,
                                exat=record.access_expires_at,
                            )
                            pipe.set(
                                self._token_key("refresh", record.refresh_digest), reference.key,
                                exat=record.expires_at,
                            )
                        pipe.set(reference.key, record.model_dump_json(), exat=record.expires_at)
                        pipe.execute()
                    except WatchError:
                        continue
                    if replay:
                        raise RejectedSession(replay=True)
                    return expires_in
        except RedisError:
            raise unavailable() from None
        raise unavailable()
