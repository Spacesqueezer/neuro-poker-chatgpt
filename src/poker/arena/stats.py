from dataclasses import dataclass, field


@dataclass
class ArenaStats:
	hands: int = 0
	seeds: list[int] = field(default_factory=list)
	results: list = field(default_factory=list)
	failed_hands: int = 0

	def record_result(self, seed, result):
		self.hands += 1
		self.seeds.append(seed)
		self.results.append(result)

	def summary(self):
		return {
			"hands": self.hands,
			"failed_hands": self.failed_hands,
		}
