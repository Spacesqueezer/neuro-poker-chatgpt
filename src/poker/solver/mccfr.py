from dataclasses import dataclass


@dataclass(frozen=True)
class MCCFRResult:
	iterations: int
	average_strategy: dict
	cumulative_regret: dict


class ExternalSamplingMCCFR:
	def __init__(self, game, seed=0):
		self.game = game
		self.seed = seed
		self.regret_sum = {}
		self.strategy_sum = {}

	def train(self, iterations):
		if iterations <= 0:
			raise ValueError("iterations must be positive")

		return MCCFRResult(
			iterations=iterations,
			average_strategy={},
			cumulative_regret={},
		)
