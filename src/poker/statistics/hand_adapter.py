from poker.statistics.collector import StatisticsCollector


class HandStatisticsAdapter:
	def __init__(self, collector=None):
		self.collector = collector or StatisticsCollector()

	def process_hand(self, hand_data):
		for player in hand_data.get("players", []):
			self.collector.register_hand(
				player["name"],
				entered_pot=player.get("entered_pot", False),
				raised_preflop=player.get("raised_preflop", False),
				three_bet=player.get("three_bet", False),
				showdown=player.get("showdown", False),
				won_showdown=player.get("won_showdown", False),
			)

		return self.collector
