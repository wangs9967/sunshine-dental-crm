import base64
import binascii
import hashlib
import hmac
import re
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import SecretStr

from app.config import AuthSettings
from app.http import APIError

PHONE_VERSION = b"\x01"
PHONE_CONTEXT = b"sunshine:members:phone:v1"
NONCE_LENGTH = 12


def _unavailable() -> APIError:
    return APIError(503, "PHONE_PROTECTION_UNAVAILABLE", "会员资料服务暂不可用，请联系门诊")


def _key(value: SecretStr | None) -> bytes:
    if value:
        try:
            key = base64.b64decode(value.get_secret_value(), altchars=b"-_", validate=True)
            if len(key) == 32:
                return key
        except (ValueError, binascii.Error):
            pass
    raise _unavailable()


def protect_phone(phone: str, settings: AuthSettings) -> tuple[bytes, bytes]:
    encryption_key = _key(settings.phone_encryption_key)
    search_key = _key(settings.phone_lookup_hmac_key)
    if hmac.compare_digest(encryption_key, search_key):
        raise _unavailable()

    value = phone.encode("ascii")
    nonce = secrets.token_bytes(NONCE_LENGTH)
    ciphertext = AESGCM(encryption_key).encrypt(nonce, value, PHONE_CONTEXT)
    return PHONE_VERSION + nonce + ciphertext, _digest(value, search_key)


def _digest(value: bytes, search_key: bytes) -> bytes:
    return hmac.digest(search_key, value, hashlib.sha256)


def phone_search_digest(phone: str, settings: AuthSettings) -> bytes:
    return _digest(phone.encode("ascii"), _key(settings.phone_lookup_hmac_key))


def mask_phone(phone: str) -> str:
    return f"{phone[:3]}****{phone[-4:]}"


def read_masked_phone(ciphertext: bytes, settings: AuthSettings) -> str:
    if not ciphertext.startswith(PHONE_VERSION):
        raise _unavailable()
    nonce_end = len(PHONE_VERSION) + NONCE_LENGTH
    try:
        phone = AESGCM(_key(settings.phone_encryption_key)).decrypt(
            ciphertext[len(PHONE_VERSION):nonce_end], ciphertext[nonce_end:], PHONE_CONTEXT,
        ).decode("ascii")
    except (InvalidTag, ValueError):
        raise _unavailable() from None
    if not re.fullmatch(r"1[3-9][0-9]{9}", phone):
        raise _unavailable()
    return mask_phone(phone)
