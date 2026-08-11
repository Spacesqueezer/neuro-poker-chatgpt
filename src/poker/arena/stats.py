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
	showdowns: int = 0
	uncontested_wins: int = 0
	pots: list[int] = field(default_factory=list)

	def record_result(self, seed, result):
		self.hands += 1
		self.seeds.append(seed)
		self.results.append(result)

		if getattr(result, "showdown", False):
			self.showdowns += 1

		if getattr(result, "uncontested", False):
			self.uncontested_wins += 1

		if getattr(result, "final_pot", None) is not None:
			self.pots.append(result.final_pot)

	def update_players(self, stacks, starting_stack):
		for name, stack in stacks.items():
			self.players[name] = PlayerArenaResult(starting_stack, stack)

	def summary(self):
		average_pot = (
			sum(self.pots) / len(self.pots)
			if self.pots
			else 0
		)

		bb_per_100 = {
			name: (
				data.profit / 2 / self.hands * 100
				if self.hands
				else 0
			)
			for name, data in self.players.items()
		}

		return {
			"hands": self.hands,
			"failed_hands": self.failed_hands,
			"showdowns": self.showdowns,
			"uncontested_wins": self.uncontested_wins,
			"average_pot": average_pot,
			"bb_per_100": bb_per_100,
			"players": {
				name: {
					"profit": data.profit,
				}
				for name, data in self.players.items()
			},
		}
