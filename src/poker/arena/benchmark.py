from dataclasses import asdict, dataclass

from poker.agents import (
	CallingStationAgent,
	ExpertAgent,
	LAGAgent,
	ManiacAgent,
	NitAgent,
	RandomAgent,
	TAGAgent,
)
from poker.arena.runner import ArenaRunner


@dataclass(frozen=True)
class ExpertBenchmarkConfig:
	sessions: int = 20
	hands_per_session: int = 100
	starting_stack: int = 200
	seed: int = 42
	equity_samples: int = 300
	opponents: tuple[str, ...] = (
		"random",
		"calling_station",
		"nit",
		"maniac",
		"tag",
		"lag",
	)

	def validate(self):
		if self.sessions <= 0:
			raise ValueError("sessions must be positive")
		if self.hands_per_session <= 0:
			raise ValueError("hands_per_session must be positive")
		if self.starting_stack <= 0:
			raise ValueError("starting_stack must be positive")
		if self.equity_samples <= 0:
			raise ValueError("equity_samples must be positive")
		if not self.opponents:
			raise ValueError("at least one opponent is required")
		if len(set(self.opponents)) != len(self.opponents):
			raise ValueError("opponents must be unique")


@dataclass(frozen=True)
class ExpertMatchupResult:
	opponent: str
	sessions: int
	requested_hands: int
	hands: int
	failed_hands: int
	expert_profit: int
	bb_per_100: float
	showdowns: int
	uncontested_wins: int

	@property
	def completion_rate(self):
		return (
			self.hands / self.requested_hands
			if self.requested_hands
			else 0.0
	)

	def to_dict(self):
		payload = asdict(self)
		payload["completion_rate"] = self.completion_rate
		return payload


@dataclass(frozen=True)
class ExpertBenchmarkResult:
	config: ExpertBenchmarkConfig
	matchups: tuple[ExpertMatchupResult, ...]

	def to_dict(self):
		return {
			"config": {
				**asdict(self.config),
				"opponents": list(self.config.opponents),
			},
			"matchups": [
				matchup.to_dict()
				for matchup in self.matchups
			],
		}


class ExpertBenchmarkRunner:
	def run(self, config):
		config.validate()
		results = []

		for opponent_index, opponent in enumerate(config.opponents):
			results.append(
				self._run_matchup(
					config,
					opponent,
					opponent_index,
				)
			)

		return ExpertBenchmarkResult(
			config=config,
			matchups=tuple(results),
		)

	def _run_matchup(self, config, opponent, opponent_index):
		total_hands = 0
		total_failed = 0
		total_profit = 0
		total_showdowns = 0
		total_uncontested = 0

		for session_index in range(config.sessions):
			agents = self._build_agents(
				config,
				opponent,
				opponent_index,
				session_index,
			)
			hand_seed = (
				config.seed
				+ opponent_index * 1_000_000
				+ session_index * config.hands_per_session
			)

			stats = ArenaRunner(
				agents,
				starting_stack=config.starting_stack,
			).run(
				hands=config.hands_per_session,
				seed=hand_seed,
			)

			total_hands += stats.hands
			total_failed += stats.failed_hands
			total_showdowns += stats.showdowns
			total_uncontested += stats.uncontested_wins
			total_profit += stats.players["expert"].profit

		bb_per_100 = (
			total_profit / 2 / total_hands * 100
			if total_hands
			else 0.0
		)

		return ExpertMatchupResult(
			opponent=opponent,
			sessions=config.sessions,
			requested_hands=(
				config.sessions * config.hands_per_session
			),
			hands=total_hands,
			failed_hands=total_failed,
			expert_profit=total_profit,
			bb_per_100=bb_per_100,
			showdowns=total_showdowns,
			uncontested_wins=total_uncontested,
		)

	def _build_agents(
		self,
		config,
		opponent,
		opponent_index,
		session_index,
	):
		base_seed = (
			config.seed
			+ opponent_index * 100_000
			+ session_index * 1_000
		)
		expert = ExpertAgent(
			seed=base_seed + 1,
			equity_samples=config.equity_samples,
		)
		baseline = self._build_opponent(
			opponent,
			base_seed + 2,
		)

		if session_index % 2 == 0:
			return {
				"expert": expert,
				opponent: baseline,
			}

		return {
			opponent: baseline,
			"expert": expert,
		}

	def _build_opponent(self, opponent, seed):
		if opponent == "random":
			return RandomAgent(seed=seed)
		if opponent == "calling_station":
			return CallingStationAgent()
		if opponent == "nit":
			return NitAgent()
		if opponent == "maniac":
			return ManiacAgent(seed=seed)
		if opponent == "tag":
			return TAGAgent(seed=seed)
		if opponent == "lag":
			return LAGAgent(seed=seed)

		raise ValueError(
			f"Unsupported benchmark opponent: {opponent}"
		)
