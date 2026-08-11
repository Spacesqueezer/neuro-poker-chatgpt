class HandStatisticsMapper:
	def map_hand(self, hand_history):
		return {
			"players": [
				self._map_player(player)
				for player in hand_history.get("players", [])
			]
		}

	def _map_player(self, player):
		return {
			"name": player["name"],
			"entered_pot": player.get("entered_pot", False),
			"raised_preflop": player.get("raised_preflop", False),
			"three_bet": player.get("three_bet", False),
			"showdown": player.get("showdown", False),
			"won_showdown": player.get("won_showdown", False),
		}
