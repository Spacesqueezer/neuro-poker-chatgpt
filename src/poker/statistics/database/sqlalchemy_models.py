from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import (
	DeclarativeBase as SQLAlchemyDeclarativeBase,
	Mapped,
	mapped_column,
	relationship,
)


class DeclarativeBase(SQLAlchemyDeclarativeBase):
	pass


class PlayerModel(DeclarativeBase):
	__tablename__ = "players"

	id: Mapped[int] = mapped_column(Integer, primary_key=True)
	name: Mapped[str] = mapped_column(
		String(128),
		nullable=False,
		unique=True,
	)
	profile_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

	statistics: Mapped[PlayerStatisticsModel | None] = relationship(
		back_populates="player",
		uselist=False,
		cascade="all, delete-orphan",
	)
	memories: Mapped[list[AgentMemoryModel]] = relationship(
		back_populates="player",
		cascade="all, delete-orphan",
	)


class PlayerStatisticsModel(DeclarativeBase):
	__tablename__ = "player_statistics"

	player_id: Mapped[int] = mapped_column(
		ForeignKey("players.id", ondelete="CASCADE"),
		primary_key=True,
	)
	hands: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	vpip: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
	pfr: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
	three_bet: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
	aggression: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
	wtsd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
	wsd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
	vpip_hands: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	pfr_hands: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	three_bet_opportunities: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	three_bets: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	fold_to_three_bet_opportunities: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	folds_to_three_bet: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	cbet_opportunities: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	cbets: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	fold_to_cbet_opportunities: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	folds_to_cbet: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	aggressive_actions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	flop_aggressive_actions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	flop_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	turn_aggressive_actions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	turn_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	river_aggressive_actions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	river_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	showdowns: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	showdown_wins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

	player: Mapped[PlayerModel] = relationship(back_populates="statistics")


class PlayerPositionStatisticsModel(DeclarativeBase):
	__tablename__ = "player_position_statistics"

	player_id: Mapped[int] = mapped_column(
		ForeignKey("players.id", ondelete="CASCADE"),
		primary_key=True,
	)
	position: Mapped[str] = mapped_column(
		String(16),
		primary_key=True,
	)
	hands: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	vpip: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
	pfr: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
	three_bet: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
	vpip_hands: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	pfr_hands: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	three_bet_opportunities: Mapped[int] = mapped_column(
		Integer,
		default=0,
		nullable=False,
	)
	three_bets: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class AgentMemoryModel(DeclarativeBase):
	__tablename__ = "agent_memory"

	agent_id: Mapped[str] = mapped_column(String(128), primary_key=True)
	player_id: Mapped[int] = mapped_column(
		ForeignKey("players.id", ondelete="CASCADE"),
		primary_key=True,
	)
	hands_observed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	vpip_estimate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
	pfr_estimate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
	aggression_estimate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
	confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

	player: Mapped[PlayerModel] = relationship(back_populates="memories")
