from dataclasses import dataclass, field


@dataclass
class PlayerArenaResult:
	starting_stack: int
	ending_stack: int

	@property
	def profit(self):
		return self.ending_stack - self.starting_stack


@dataclass
class ArenaStats:
	hands: int = 0
	seeds: list[int] = field(default_factory=list)
	results: list = field(default_factory=list)
	failed_hands: int = 0
	players: dict[str, PlayerArenaResult] = field(default_factory=dict)

	def record_result(self, seed, result):
		self.hands += 1
		self.seeds.append(seed)
		self.results.append(result)

	def summary(self):
		return {
			"hands": self.hands,
			"failed_hands": self.failed_hands,
			"players": {
				name: {
					"profit": data.profit,
				}
				for name, data in self.players.items()
			},
		}
