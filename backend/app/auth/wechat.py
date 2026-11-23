import json
from contextlib import closing
from http.client import HTTPException, HTTPSConnection
from urllib.parse import urlencode

from app.config import AuthSettings
from app.http import APIError


def exchange_code(code: str, settings: AuthSettings) -> str:
    secret = settings.wechat_app_secret
    if not settings.wechat_app_id or not secret or not secret.get_secret_value():
        raise APIError(503, "WECHAT_NOT_CONFIGURED", "微信登录暂不可用，请联系门诊")

    query = urlencode({
        "appid": settings.wechat_app_id,
        "secret": secret.get_secret_value(),
        "js_code": code,
        "grant_type": "authorization_code",
    })
    failure = APIError(502, "WECHAT_UNAVAILABLE", "微信登录服务暂不可用，请稍后重试")
    try:
        # Fixed TLS host, bounded response, and no HTTP client URL logging or redirects.
        with closing(HTTPSConnection("api.weixin.qq.com", timeout=5)) as connection:
            connection.request("GET", "/sns/jscode2session?" + query)
            response = connection.getresponse()
            if response.status != 200:
                raise failure
            payload = json.loads(response.read(8192))
    except (OSError, HTTPException, ValueError):
        raise failure from None

    if not isinstance(payload, dict):
        raise failure
    if payload.get("errcode") in (40029, 40163):
        raise APIError(400, "WECHAT_CODE_INVALID", "微信登录凭据已失效，请重新点击微信登录")
    if payload.get("errcode", 0) != 0:
        raise failure
    openid = payload.get("openid")
    if not isinstance(openid, str) or not openid.strip() or len(openid) > 128 or "\x00" in openid:
        raise failure
    return openid
