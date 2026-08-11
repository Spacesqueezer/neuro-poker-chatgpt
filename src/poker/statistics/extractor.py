from poker.statistics.events import PlayerHandEvent


class HandStatisticsExtractor:
	def extract(self, hand_history):
		return [
			self._extract_player(player)
			for player in hand_history.get("players", [])
		]

	def _extract_player(self, player):
		return PlayerHandEvent(
			player_name=player["name"],
			position=player.get("position"),
			street_actions=tuple(player.get("street_actions", [])),
			entered_pot=player.get("entered_pot", False),
			raised_preflop=player.get("raised_preflop", False),
			three_bet=player.get("three_bet", False),
			showdown=player.get("showdown", False),
			won_showdown=player.get("won_showdown", False),
		)
