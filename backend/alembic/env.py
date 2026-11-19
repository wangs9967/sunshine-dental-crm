from alembic import context
from sqlalchemy import create_engine, pool

from app.config import LocalSettings
from app.db.models import Base


def run_migrations() -> None:
    database_url = LocalSettings().database_url
    if context.is_offline_mode():
        context.configure(
            url=database_url,
            target_metadata=Base.metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = create_engine(database_url, poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=Base.metadata,
                compare_type=True,
                compare_server_default=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


run_migrations()
