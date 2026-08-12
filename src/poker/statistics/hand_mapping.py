class HandStatisticsMapper:
	PREFLOP = "preflop"
	VOLUNTARY_ACTIONS = {"call", "bet", "raise", "all_in"}
	RAISE_ACTIONS = {"bet", "raise", "all_in"}

	def map_hand(self, hand_history):
		if hasattr(hand_history, "to_dict"):
			hand_history = hand_history.to_dict()

		players = {
			player["name"]: self._map_player(player)
			for player in hand_history.get("players", [])
		}

		preflop_raise_count = 0

		for event in hand_history.get("events", []):
			if hasattr(event, "to_dict"):
				event = event.to_dict()

			event_type = event.get("type")
			data = event.get("data", {})

			if event_type == "action":
				player_name = data.get("player")
				if player_name not in players:
					continue

				action = data.get("action")
				street = data.get("street")

				players[player_name]["street_actions"].append(
					{
						"street": street,
						"action": action,
					}
				)

				if street == self.PREFLOP:
					if action in self.VOLUNTARY_ACTIONS:
						players[player_name]["entered_pot"] = True

					if action in self.RAISE_ACTIONS:
						preflop_raise_count += 1
						players[player_name]["raised_preflop"] = True

						if preflop_raise_count == 2:
							players[player_name]["three_bet"] = True

			elif event_type == "showdown":
				results = data.get("results", {})
				for player_name, result in results.items():
					if player_name not in players:
						continue

					players[player_name]["showdown"] = True
					if result.get("payout", 0) > 0:
						players[player_name]["won_showdown"] = True

		return {
			"players": list(players.values()),
		}

	def _map_player(self, player):
		return {
			"name": player["name"],
			"position": player.get("position"),
			"street_actions": list(player.get("street_actions", [])),
			"entered_pot": player.get("entered_pot", False),
			"raised_preflop": player.get("raised_preflop", False),
			"three_bet": player.get("three_bet", False),
			"showdown": player.get("showdown", False),
			"won_showdown": player.get("won_showdown", False),
		}
