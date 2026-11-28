from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis import Redis

from app.access_routes import router as access_router
from app.auth.routes import members_router, router
from app.auth.sessions import SessionService
from app.config import AuthSettings
from app.db.session import database_engine
from app.followups import router as followup_router
from app.http import install_http_handlers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = AuthSettings()
    with Redis(
        host=settings.redis_host, port=settings.redis_port, db=settings.redis_db,
        password=settings.redis_password.get_secret_value() if settings.redis_password else None,
        socket_connect_timeout=2, socket_timeout=2, decode_responses=True,
    ) as cache:
        app.state.auth_sessions = SessionService(cache, settings)
        app.state.auth_settings = settings
        try:
            yield
        finally:
            del app.state.auth_sessions
            del app.state.auth_settings
            if database_engine.cache_info().currsize:
                database_engine().dispose()
                database_engine.cache_clear()


app = FastAPI(title="阳光口腔会员运营管理系统 API", version="0.1.0", lifespan=lifespan)
install_http_handlers(app)
app.include_router(router)
app.include_router(members_router)
app.include_router(access_router)
app.include_router(followup_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
