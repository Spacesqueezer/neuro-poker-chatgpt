from dataclasses import dataclass
import json
from pathlib import Path

@dataclass(frozen=True)
class SolverTrainingExample:
	observation: tuple[float, ...]
	legal_mask: tuple[float, ...]
	probabilities: tuple[float, ...]
	acting_player: str
	opponent_order: tuple[str, ...]
	source: str

class SolverTrainingObjectiveContract:
	"""Framework-neutral semantics for solver soft-policy training."""

	action_count = 6

	@classmethod
	def validate_target(cls, legal_mask, probabilities):
		if len(legal_mask) != cls.action_count:
			raise ValueError("legal mask must contain six actions")
		if len(probabilities) != cls.action_count:
			raise ValueError("probabilities must contain six actions")
		if abs(sum(probabilities) - 1.0) > 1e-9:
			raise ValueError("probabilities must sum to one")


class SolverTrainingInput:
	def observation_sizes(self):
		return {len(example.observation) for example in self.examples}

	def to_batch(self):
		from poker.solver.training_batch import build_solver_training_batch

		return build_solver_training_batch(self.examples)

	def __init__(self, examples):
		self.examples = tuple(examples)
		if not self.examples:
			raise ValueError('solver training input is empty')

	@classmethod
	def load(cls, path):
		examples = []
		for line in Path(path).read_text(encoding='utf-8').splitlines():
			payload = json.loads(line)
			examples.append(SolverTrainingExample(
				observation=tuple(float(x) for x in payload['observation']),
				legal_mask=tuple(float(x) for x in payload['legal_mask']),
				probabilities=tuple(float(x) for x in payload['probabilities']),
				acting_player=payload['acting_player'],
				opponent_order=tuple(payload['opponent_order']),
				source=payload['source'],
			))
		return cls(examples)
