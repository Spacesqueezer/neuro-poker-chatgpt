class HandStatisticsMapper:
	PREFLOP = "preflop"
	FLOP = "flop"
	POSTFLOP_STREETS = {"flop", "turn", "river"}
	VOLUNTARY_ACTIONS = {"call", "bet", "raise", "all_in"}
	RAISE_ACTIONS = {"bet", "raise", "all_in"}
	AGGRESSIVE_ACTIONS = {"bet", "raise", "all_in"}

	def map_hand(self, hand_history):
		if hasattr(hand_history, "to_dict"):
			hand_history = hand_history.to_dict()

		players = {
			player["name"]: self._map_player(player)
			for player in hand_history.get("players", [])
		}

		preflop_raise_count = 0
		preflop_aggressor = None
		open_raiser = None
		three_bettor = None
		flop_bet_seen = False
		flop_aggressor_acted = False
		cbet_bettor = None
		cbet_responses = set()
		cbet_raised = False

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
				player = players[player_name]

				player["street_actions"].append(
					{
						"street": street,
						"action": action,
					}
				)

				if street == self.PREFLOP:
					if action in self.VOLUNTARY_ACTIONS:
						player["entered_pot"] = True

					if preflop_raise_count == 1 and player_name != open_raiser:
						player["three_bet_opportunity"] = True

					if preflop_raise_count == 2 and player_name == open_raiser:
						player["fold_to_three_bet_opportunity"] = True
						if action == "fold":
							player["folded_to_three_bet"] = True

					if action in self.RAISE_ACTIONS:
						preflop_raise_count += 1
						player["raised_preflop"] = True
						preflop_aggressor = player_name

						if preflop_raise_count == 1:
							open_raiser = player_name
						elif preflop_raise_count == 2:
							three_bettor = player_name
							player["three_bet"] = True

				elif street in self.POSTFLOP_STREETS:
					if action in self.AGGRESSIVE_ACTIONS:
						player["aggressive_actions"] += 1
						player[f"{street}_aggressive_actions"] += 1
					elif action == "call":
						player["calls"] += 1
						player[f"{street}_calls"] += 1

					if street == self.FLOP:
						if (
							cbet_bettor is not None
							and player_name != cbet_bettor
							and player_name not in cbet_responses
							and not cbet_raised
						):
							player["fold_to_cbet_opportunity"] = True
							cbet_responses.add(player_name)

							if action == "fold":
								player["folded_to_cbet"] = True

							if action in {"raise", "all_in"}:
								cbet_raised = True

						if player_name == preflop_aggressor and not flop_aggressor_acted:
							flop_aggressor_acted = True

							if not flop_bet_seen:
								player["cbet_opportunity"] = True
								if action in {"bet", "all_in"}:
									player["cbet"] = True
									cbet_bettor = player_name

						if action in self.AGGRESSIVE_ACTIONS:
							flop_bet_seen = True

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
			"three_bet_opportunity": player.get("three_bet_opportunity", False),
			"three_bet": player.get("three_bet", False),
			"fold_to_three_bet_opportunity": player.get(
				"fold_to_three_bet_opportunity",
				False,
			),
			"folded_to_three_bet": player.get("folded_to_three_bet", False),
			"cbet_opportunity": player.get("cbet_opportunity", False),
			"cbet": player.get("cbet", False),
			"fold_to_cbet_opportunity": player.get(
				"fold_to_cbet_opportunity",
				False,
			),
			"folded_to_cbet": player.get("folded_to_cbet", False),
			"aggressive_actions": player.get("aggressive_actions", 0),
			"calls": player.get("calls", 0),
			"flop_aggressive_actions": player.get("flop_aggressive_actions", 0),
			"flop_calls": player.get("flop_calls", 0),
			"turn_aggressive_actions": player.get("turn_aggressive_actions", 0),
			"turn_calls": player.get("turn_calls", 0),
			"river_aggressive_actions": player.get("river_aggressive_actions", 0),
			"river_calls": player.get("river_calls", 0),
			"showdown": player.get("showdown", False),
			"won_showdown": player.get("won_showdown", False),
		}
