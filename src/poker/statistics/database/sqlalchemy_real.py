from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
	pass


class PlayerORM(Base):
	__tablename__ = "players"

	id: Mapped[int] = mapped_column(primary_key=True)
	name: Mapped[str]
	profile_id: Mapped[int | None]


class PlayerStatisticsORM(Base):
	__tablename__ = "player_statistics"

	player_id: Mapped[int] = mapped_column(primary_key=True)
	hands: Mapped[int] = mapped_column(default=0)
	vpip: Mapped[float] = mapped_column(default=0.0)
	pfr: Mapped[float] = mapped_column(default=0.0)


class AgentMemoryORM(Base):
	__tablename__ = "agent_memory"

	agent_id: Mapped[str] = mapped_column(primary_key=True)
	player_id: Mapped[int] = mapped_column(primary_key=True)
	confidence: Mapped[float] = mapped_column(default=0.0)
