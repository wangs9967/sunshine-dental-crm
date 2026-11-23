from redis import Redis
from sqlalchemy import create_engine, text

from app.config import LocalSettings


def main() -> None:
    settings = LocalSettings()
    engine = create_engine(settings.database_url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            postgres_version = str(connection.execute(text("SHOW server_version")).scalar_one())
    finally:
        engine.dispose()

    with Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=settings.redis_password.get_secret_value() if settings.redis_password else None,
        socket_connect_timeout=5,
        socket_timeout=5,
    ) as cache:
        cache.ping()
        redis_version = cache.info("server")["redis_version"]

    print(f"PostgreSQL {postgres_version} connected")
    print(f"Redis {redis_version} connected")


if __name__ == "__main__":
    main()
