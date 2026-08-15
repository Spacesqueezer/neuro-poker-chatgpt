from dataclasses import dataclass

from poker.solver.teacher import validate_teacher_record_export


SOLVER_TARGET_ACTIONS = (
	"fold",
	"check",
	"call",
	"bet",
	"raise",
	"all_in",
)


@dataclass(frozen=True)
class SolverLearningTarget:
	information_set: dict
	action_names: tuple[str, ...]
	legal_mask: tuple[float, ...]
	probabilities: tuple[float, ...]
	solver_action_groups: tuple[tuple[str, ...], ...]
	source: str

	@property
	def size(self):
		return len(self.action_names)


def solver_action_category(action):
	if action in {
		"fold",
		"check",
		"call",
		"raise",
		"all_in",
	}:
		return action

	if action.startswith("bet_") and action.endswith("bb"):
		size = action[len("bet_"):-len("bb")]
		try:
			value = int(size)
		except ValueError as error:
			raise ValueError(
				f"unsupported solver action: {action}"
			) from error
		if value <= 0:
			raise ValueError(
				f"unsupported solver action: {action}"
			)
		return "bet"

	raise ValueError(f"unsupported solver action: {action}")


def build_learning_targets(teacher_payload):
	validate_teacher_record_export(teacher_payload)
	return tuple(
		teacher_record_to_learning_target(record)
		for record in teacher_payload["records"]
	)


def teacher_record_to_learning_target(record):
	groups = {
		action: []
		for action in SOLVER_TARGET_ACTIONS
	}
	probabilities = {
		action: 0.0
		for action in SOLVER_TARGET_ACTIONS
	}

	for solver_action in record["legal_actions"]:
		category = solver_action_category(solver_action)
		groups[category].append(solver_action)
		probabilities[category] += record[
			"action_probabilities"
		][solver_action]

	legal_mask = tuple(
		1.0 if groups[action] else 0.0
		for action in SOLVER_TARGET_ACTIONS
	)
	target_probabilities = tuple(
		probabilities[action]
		for action in SOLVER_TARGET_ACTIONS
	)

	if abs(sum(target_probabilities) - 1.0) > 1e-9:
		raise ValueError(
			"solver learning target probabilities must sum to 1"
		)

	return SolverLearningTarget(
		information_set=dict(record["information_set"]),
		action_names=SOLVER_TARGET_ACTIONS,
		legal_mask=legal_mask,
		probabilities=target_probabilities,
		solver_action_groups=tuple(
			tuple(groups[action])
			for action in SOLVER_TARGET_ACTIONS
		),
		source=record["source"],
	)
