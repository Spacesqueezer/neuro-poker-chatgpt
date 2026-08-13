from poker.statistics.collector import StatisticsCollector
from poker.statistics.hand_mapping import HandStatisticsMapper


class HandStatisticsAdapter:
	def __init__(self, collector=None, mapper=None):
		self.collector = collector or StatisticsCollector()
		self.mapper = mapper or HandStatisticsMapper()

	def process_hand(self, hand_history):
		hand_data = self.mapper.map_hand(hand_history)

		for player in hand_data.get("players", []):
			self.collector.register_hand(
				player["name"],
				entered_pot=player.get("entered_pot", False),
				raised_preflop=player.get("raised_preflop", False),
				three_bet_opportunity=player.get("three_bet_opportunity", False),
				three_bet=player.get("three_bet", False),
				fold_to_three_bet_opportunity=player.get(
					"fold_to_three_bet_opportunity",
					False,
				),
				folded_to_three_bet=player.get("folded_to_three_bet", False),
				cbet_opportunity=player.get("cbet_opportunity", False),
				cbet=player.get("cbet", False),
				aggressive_actions=player.get("aggressive_actions", 0),
				calls=player.get("calls", 0),
				showdown=player.get("showdown", False),
				won_showdown=player.get("won_showdown", False),
				position=player.get("position"),
			)

		return self.collector
