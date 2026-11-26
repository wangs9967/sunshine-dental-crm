from typing import Literal

from app.auth.identity import Role
from app.http import APIError

Permission = Literal[
    "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "R11", "R12",
    "R13", "R14", "R15", "R16", "R17", "R17_WRITE", "R18", "R18_WRITE",
]

MANAGEMENT: frozenset[Role | None] = frozenset({"manager", "admin"})
STAFF: frozenset[Role | None] = frozenset({"manager", "admin", "employee"})
MEMBER: frozenset[Role | None] = frozenset({"member"})

ALLOWED: dict[Permission, frozenset[Role | None]] = {
    "R1": frozenset({None}),  # The registration route checks the WeChat channel and account.
    "R2": MEMBER,
    "R3": frozenset(),
    "R4": MEMBER,
    "R5": STAFF,
    "R6": STAFF,
    "R7": MANAGEMENT,
    "R8": STAFF,
    "R9": MANAGEMENT,
    "R10": MANAGEMENT,
    "R11": MANAGEMENT,
    "R12": MANAGEMENT,
    "R13": frozenset({"admin"}),
    "R14": frozenset(),
    "R15": frozenset({"admin"}),
    "R16": frozenset({"admin"}),
    "R17": frozenset({"admin"}),
    "R17_WRITE": frozenset(),  # No configuration keys have been approved for writes.
    "R18": frozenset({"admin"}),
    "R18_WRITE": frozenset(),
}

PENDING: dict[Permission, frozenset[Role | None]] = {
    "R3": MEMBER,
    "R10": frozenset({"employee"}),
    "R13": frozenset({"manager"}),
    "R14": MANAGEMENT,
    "R15": frozenset({"manager"}),
    "R16": frozenset({"manager"}),
    "R17": frozenset({"manager"}),
    "R17_WRITE": MANAGEMENT,
    "R18": frozenset({"manager"}),
}


def check_permission(permission: Permission, role: Role | None) -> None:
    if role in ALLOWED[permission]:
        return
    if role in PENDING.get(permission, frozenset()):
        raise APIError(403, "FEATURE_NOT_AVAILABLE", "该功能暂未开放")
    raise APIError(403, "FORBIDDEN", "当前身份无权使用此功能")
