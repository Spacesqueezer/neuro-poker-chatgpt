"""Optional statistics storage for command-line sessions."""

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from poker.statistics.database.facade import StatisticsFacade
from poker.statistics.database.services import StatisticsService
from poker.statistics.database.sqlalchemy_models import DeclarativeBase
from poker.statistics.database.sqlalchemy_repositories import (
    SQLAlchemyMemoryRepository,
    SQLAlchemyPlayerRepository,
    SQLAlchemyStatisticsRepository,
)


@contextmanager
def statistics_connection() -> Iterator[tuple[Session | None, StatisticsFacade | None]]:
    """Open POKER_DATABASE_URL, releasing the session and pool even on failure.

    Without a URL, callers continue with in-memory gameplay. create_all supports
    new databases only; existing schemas still require Alembic migrations.
    """
    url = os.getenv("POKER_DATABASE_URL")
    if not url:
        yield None, None
        return

    engine = create_engine(url, pool_pre_ping=True, pool_recycle=3600)
    try:
        DeclarativeBase.metadata.create_all(engine)
        with Session(engine) as session:
            service = StatisticsService(
                player_repository=SQLAlchemyPlayerRepository(session),
                statistics_repository=SQLAlchemyStatisticsRepository(session),
                memory_repository=SQLAlchemyMemoryRepository(session),
            )
            yield session, StatisticsFacade(service)
    finally:
        engine.dispose()
