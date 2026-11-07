import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from poker.statistics.database import connection
from poker.statistics.database.records import PlayerRecord
from poker.statistics.database.sqlalchemy_models import PlayerModel


def test_optional_database_without_url(monkeypatch):
    monkeypatch.delenv("POKER_DATABASE_URL", raising=False)
    with connection.statistics_connection() as (session, facade):
        assert session is None and facade is None


def test_statistics_connection_persists_records(monkeypatch, tmp_path):
    monkeypatch.setenv("POKER_DATABASE_URL", f"sqlite:///{tmp_path / 'statistics.db'}")
    with connection.statistics_connection() as (_, facade):
        facade.service.player_repository.save(PlayerRecord(id=1, name="Hero"))
    with connection.statistics_connection() as (_, facade):
        assert facade.service.player_repository.get(1).name == "Hero"


def test_failed_command_rolls_back_and_disposes_pool(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'statistics.db'}"
    monkeypatch.setenv("POKER_DATABASE_URL", url)
    disposed = []

    def create_observed_engine(*args, **kwargs):
        engine = create_engine(*args, **kwargs)
        event.listen(engine, "engine_disposed", lambda engine: disposed.append(True))
        return engine

    monkeypatch.setattr(connection, "create_engine", create_observed_engine)
    with pytest.raises(RuntimeError, match="command failed"):
        with connection.statistics_connection() as (session, _):
            session.add(PlayerModel(id=1, name="Uncommitted"))
            session.flush()
            raise RuntimeError("command failed")
    assert disposed == [True]
    engine = create_engine(url)
    try:
        with Session(engine) as session:
            assert session.scalars(select(PlayerModel)).all() == []
    finally:
        engine.dispose()
