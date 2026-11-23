from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config import LocalSettings


@lru_cache(maxsize=1)
def database_engine() -> Engine:
    return create_engine(LocalSettings().database_url, pool_pre_ping=True, hide_parameters=True)


def get_db() -> Iterator[Session]:
    with Session(database_engine()) as db:
        yield db
