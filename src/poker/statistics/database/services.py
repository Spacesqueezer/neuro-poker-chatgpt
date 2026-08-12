from poker.statistics.database.models import PlayerStatisticsRecord


class StatisticsService:
	_COUNTER_FIELDS = (
		"hands",
		"vpip_hands",
		"pfr_hands",
		"three_bet_opportunities",
		"three_bets",
		"fold_to_three_bet_opportunities",
		"folds_to_three_bet",
		"cbet_opportunities",
		"cbets",
		"aggressive_actions",
		"calls",
		"showdowns",
		"showdown_wins",
	)

	def __init__(
		self,
		player_repository,
		statistics_repository,
		memory_repository,
	):
		self.player_repository = player_repository
		self.statistics_repository = statistics_repository
		self.memory_repository = memory_repository

	def get_player_statistics(self, player_id):
		return self.statistics_repository.get(player_id)

	def get_agent_memory(self, agent_id, player_id):
		return self.memory_repository.get(agent_id, player_id)

	def persist_collector(self, collector, player_ids):
		records = []

		for player_name, stats in collector.players.items():
			if player_name not in player_ids:
				raise KeyError(
					f"Missing persistent player id for {player_name}"
				)

			player_id = player_ids[player_name]
			incoming = self._record_from_statistics(
				player_id,
				stats,
			)
			existing = self.statistics_repository.get(player_id)
			record = self._merge_records(existing, incoming)

			self.statistics_repository.save(record)
			records.append(record)

		return records

	def _record_from_statistics(self, player_id, stats):
		return PlayerStatisticsRecord(
			player_id=player_id,
			hands=stats.hands,
			vpip=stats.vpip,
			pfr=stats.pfr,
			three_bet=stats.three_bet,
			aggression=stats.aggression_factor,
			wtsd=stats.wtsd,
			wsd=stats.wsd,
			vpip_hands=stats.vpip_hands,
			pfr_hands=stats.pfr_hands,
			three_bet_opportunities=stats.three_bet_opportunities,
			three_bets=stats.three_bets,
			fold_to_three_bet_opportunities=(
				stats.fold_to_three_bet_opportunities
			),
			folds_to_three_bet=stats.folds_to_three_bet,
			cbet_opportunities=stats.cbet_opportunities,
			cbets=stats.cbets,
			aggressive_actions=stats.aggressive_actions,
			calls=stats.calls,
			showdowns=stats.showdowns,
			showdown_wins=stats.showdown_wins,
		)

	def _merge_records(self, existing, incoming):
		if existing is None:
			return incoming

		counters = {
			field: getattr(existing, field) + getattr(incoming, field)
			for field in self._COUNTER_FIELDS
		}

		return PlayerStatisticsRecord(
			player_id=incoming.player_id,
			**counters,
			vpip=self._ratio(
				counters["vpip_hands"],
				counters["hands"],
			),
			pfr=self._ratio(
				counters["pfr_hands"],
				counters["hands"],
			),
			three_bet=self._ratio(
				counters["three_bets"],
				counters["three_bet_opportunities"],
			),
			aggression=self._aggression(
				counters["aggressive_actions"],
				counters["calls"],
			),
			wtsd=self._ratio(
				counters["showdowns"],
				counters["hands"],
			),
			wsd=self._ratio(
				counters["showdown_wins"],
				counters["showdowns"],
			),
		)

	def _ratio(self, numerator, denominator):
		return numerator / denominator if denominator else 0

	def _aggression(self, aggressive_actions, calls):
		return (
			aggressive_actions / calls
			if calls
			else float(aggressive_actions)
		)
