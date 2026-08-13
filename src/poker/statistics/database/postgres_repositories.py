from poker.statistics.database.models import (
	AgentMemoryRecord,
	PlayerRecord,
	PlayerStatisticsRecord,
)
from poker.statistics.database.repositories import (
	AgentMemoryRepository,
	PlayerRepository,
	StatisticsRepository,
)
from sqlalchemy import func, select

from poker.statistics.database.sqlalchemy_models import (
	AgentMemoryModel,
	PlayerModel,
	PlayerStatisticsModel,
)


class PostgresPlayerRepository(PlayerRepository):
	def __init__(self, session):
		self.session = session

	def save(self, player: PlayerRecord):
		self.session.merge(
			PlayerModel(
				id=player.id,
				name=player.name,
				profile_id=player.profile_id,
			)
		)
		self.session.commit()

	def get(self, player_id: int):
		model = self.session.get(PlayerModel, player_id)
		if model is None:
			return None

		return self._to_record(model)

	def get_by_name(self, name: str):
		model = self.session.scalar(
			select(PlayerModel).where(PlayerModel.name == name)
		)
		if model is None:
			return None

		return self._to_record(model)

	def next_id(self):
		current_max = self.session.scalar(
			select(func.max(PlayerModel.id))
		)
		return (current_max or 0) + 1

	def _to_record(self, model):
		return PlayerRecord(
			id=model.id,
			name=model.name,
			profile_id=model.profile_id,
		)


class PostgresStatisticsRepository(StatisticsRepository):
	def __init__(self, session):
		self.session = session

	def save(self, statistics: PlayerStatisticsRecord):
		self.session.merge(
			PlayerStatisticsModel(
				player_id=statistics.player_id,
				hands=statistics.hands,
				vpip=statistics.vpip,
				pfr=statistics.pfr,
				three_bet=statistics.three_bet,
				aggression=statistics.aggression,
				wtsd=statistics.wtsd,
				wsd=statistics.wsd,
				vpip_hands=statistics.vpip_hands,
				pfr_hands=statistics.pfr_hands,
				three_bet_opportunities=statistics.three_bet_opportunities,
				three_bets=statistics.three_bets,
				fold_to_three_bet_opportunities=statistics.fold_to_three_bet_opportunities,
				folds_to_three_bet=statistics.folds_to_three_bet,
				cbet_opportunities=statistics.cbet_opportunities,
				cbets=statistics.cbets,
				aggressive_actions=statistics.aggressive_actions,
				calls=statistics.calls,
				showdowns=statistics.showdowns,
				showdown_wins=statistics.showdown_wins,
			)
		)
		self.session.commit()

	def get(self, player_id: int):
		model = self.session.get(PlayerStatisticsModel, player_id)
		if model is None:
			return None

		return PlayerStatisticsRecord(
			player_id=model.player_id,
			hands=model.hands,
			vpip=model.vpip,
			pfr=model.pfr,
			three_bet=model.three_bet,
			aggression=model.aggression,
			wtsd=model.wtsd,
			wsd=model.wsd,
			vpip_hands=model.vpip_hands,
			pfr_hands=model.pfr_hands,
			three_bet_opportunities=model.three_bet_opportunities,
			three_bets=model.three_bets,
			fold_to_three_bet_opportunities=model.fold_to_three_bet_opportunities,
			folds_to_three_bet=model.folds_to_three_bet,
			cbet_opportunities=model.cbet_opportunities,
			cbets=model.cbets,
			aggressive_actions=model.aggressive_actions,
			calls=model.calls,
			showdowns=model.showdowns,
			showdown_wins=model.showdown_wins,
		)


class PostgresMemoryRepository(AgentMemoryRepository):
	def __init__(self, session):
		self.session = session

	def save(self, memory: AgentMemoryRecord):
		self.session.merge(
			AgentMemoryModel(
				agent_id=memory.agent_id,
				player_id=memory.player_id,
				hands_observed=memory.hands_observed,
				vpip_estimate=memory.vpip_estimate,
				pfr_estimate=memory.pfr_estimate,
				aggression_estimate=memory.aggression_estimate,
				confidence=memory.confidence,
			)
		)
		self.session.commit()

	def get(self, agent_id: str, player_id: int):
		model = self.session.get(
			AgentMemoryModel,
			(agent_id, player_id),
		)
		if model is None:
			return None

		return AgentMemoryRecord(
			agent_id=model.agent_id,
			player_id=model.player_id,
			hands_observed=model.hands_observed,
			vpip_estimate=model.vpip_estimate,
			pfr_estimate=model.pfr_estimate,
			aggression_estimate=model.aggression_estimate,
			confidence=model.confidence,
		)
