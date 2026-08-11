from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
	pass


class PlayerORM(Base):
	__tablename__ = "players"

	id: Mapped[int] = mapped_column(primary_key=True)
	name: Mapped[str]

	statistics: Mapped[list["PlayerStatisticsORM"]] = relationship(
		back_populates="player"
	)

	memories: Mapped[list["AgentMemoryORM"]] = relationship(
		back_populates="player"
	)


class PlayerStatisticsORM(Base):
	__tablename__ = "player_statistics"

	id: Mapped[int] = mapped_column(primary_key=True)
	player_id: Mapped[int] = mapped_column(
		ForeignKey("players.id")
	)

	vpip: Mapped[float] = mapped_column(default=0.0)
	pfr: Mapped[float] = mapped_column(default=0.0)

	player: Mapped["PlayerORM"] = relationship(
		back_populates="statistics"
	)


class AgentMemoryORM(Base):
	__tablename__ = "agent_memory"

	id: Mapped[int] = mapped_column(primary_key=True)
	agent_id: Mapped[str]
	player_id: Mapped[int] = mapped_column(
		ForeignKey("players.id")
	)

	confidence: Mapped[float] = mapped_column(default=0.0)

	player: Mapped["PlayerORM"] = relationship(
		back_populates="memories"
	)
