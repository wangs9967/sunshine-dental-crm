import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.profiles import RFC_9106_LOW_MEMORY

PASSWORD_HASHER = PasswordHasher.from_parameters(RFC_9106_LOW_MEMORY)
# Give missing credentials a verification of the same cost as a current stored hash.
DUMMY_PASSWORD_HASH = PASSWORD_HASHER.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, stored_hash: str | None) -> bool:
    is_argon2id = stored_hash is not None and stored_hash.startswith("$argon2id$")
    try:
        PASSWORD_HASHER.verify(stored_hash if is_argon2id and stored_hash else DUMMY_PASSWORD_HASH, password)
    except VerifyMismatchError:
        return False
    except (InvalidHashError, VerificationError):
        # A malformed credential record must follow the same denial path as an unknown account.
        try:
            PASSWORD_HASHER.verify(DUMMY_PASSWORD_HASH, password)
        except VerifyMismatchError:
            pass
        return False
    return is_argon2id
