from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class SolverDatasetRecord:
	observation: list[float]
	action_probabilities: list[float]


class SolverDatasetLoader:
	def load(self, path: str | Path):
		records = []
		with Path(path).open("r", encoding="utf-8") as file:
			for line in file:
				if not line.strip():
					continue
				data = json.loads(line)
				records.append(
					SolverDatasetRecord(
						observation=data["observation"],
						action_probabilities=data["action_probabilities"],
					)
				)
		return records
