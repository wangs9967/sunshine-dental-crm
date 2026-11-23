import base64
import binascii
import hashlib
import hmac
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import SecretStr

from app.config import AuthSettings
from app.http import APIError


def _key(value: SecretStr | None) -> bytes:
    if value:
        try:
            key = base64.b64decode(value.get_secret_value(), altchars=b"-_", validate=True)
            if len(key) == 32:
                return key
        except (ValueError, binascii.Error):
            pass
    raise APIError(503, "PHONE_PROTECTION_UNAVAILABLE", "会员资料服务暂不可用，请联系门诊")


def protect_phone(phone: str, settings: AuthSettings) -> tuple[bytes, bytes]:
    encryption_key = _key(settings.phone_encryption_key)
    search_key = _key(settings.phone_lookup_hmac_key)
    if hmac.compare_digest(encryption_key, search_key):
        raise APIError(503, "PHONE_PROTECTION_UNAVAILABLE", "会员资料服务暂不可用，请联系门诊")

    value = phone.encode("ascii")
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(encryption_key).encrypt(nonce, value, b"sunshine:members:phone:v1")
    return b"\x01" + nonce + ciphertext, hmac.digest(search_key, value, hashlib.sha256)
