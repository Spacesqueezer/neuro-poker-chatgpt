from dataclasses import dataclass

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from poker.statistics.database.sqlalchemy_models import DeclarativeBase


@dataclass(frozen=True)
class SQLAlchemyConfig:
	url: str
	echo: bool = False
	create_schema: bool = False


class SQLAlchemyEngine:
	def __init__(self, config: SQLAlchemyConfig):
		self.config = config
		self.raw_engine: Engine = create_engine(
			config.url,
			echo=config.echo,
		)
		self._session_factory = sessionmaker(
			bind=self.raw_engine,
			expire_on_commit=False,
		)

		if config.create_schema:
			self.create_schema()

	def create_schema(self):
		DeclarativeBase.metadata.create_all(self.raw_engine)

	def create_session(self) -> Session:
		return self._session_factory()

	def dispose(self):
		self.raw_engine.dispose()


SQLAlchemySession = Session
