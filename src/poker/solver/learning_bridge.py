from dataclasses import dataclass

from poker.solver.learning_target import (
	SolverLearningTarget,
	build_learning_targets,
)
from poker.solver.observation_compatibility import (
	build_observation_compatibility_report,
)


@dataclass(frozen=True)
class SolverBridgeObservation:
	player_index: int
	street: str
	hole_cards: tuple[tuple[int, str], ...]
	public_board: tuple[tuple[int, str], ...]
	hero_starting_stack: int
	hero_total_contribution: int
	hero_remaining_chips: int
	opponent_starting_stack: int
	opponent_total_contribution: int
	opponent_remaining_chips: int
	opponent_present: bool
	opponent_folded: bool
	absent_opponent_slots: tuple[int, ...]


@dataclass(frozen=True)
class SolverLearningBridgeRecord:
	observation: SolverBridgeObservation
	target: SolverLearningTarget
	omitted_production_features: tuple[str, ...]


def build_learning_bridge_records(teacher_payload):
	targets = build_learning_targets(teacher_payload)
	compatibility = build_observation_compatibility_report()
	omitted = compatibility.unavailable_features

	return tuple(
		SolverLearningBridgeRecord(
			observation=_bridge_observation(target),
			target=target,
			omitted_production_features=omitted,
		)
		for target in targets
	)


def _bridge_observation(target):
	info = target.information_set
	player = info["player"]
	opponent = 1 - player
	starting_stacks = tuple(info["starting_stacks"])
	commitments = tuple(info["commitments"])

	return SolverBridgeObservation(
		player_index=player,
		street=info["street"],
		hole_cards=tuple(
			(card["rank"], card["suit"])
			for card in info["hole_cards"]
		),
		public_board=tuple(
			(card["rank"], card["suit"])
			for card in info["public_board"]
		),
		hero_starting_stack=starting_stacks[player],
		hero_total_contribution=commitments[player],
		hero_remaining_chips=(
			starting_stacks[player] - commitments[player]
		),
		opponent_starting_stack=starting_stacks[opponent],
		opponent_total_contribution=commitments[opponent],
		opponent_remaining_chips=(
			starting_stacks[opponent] - commitments[opponent]
		),
		opponent_present=True,
		opponent_folded=False,
		absent_opponent_slots=tuple(range(1, 8)),
	)
