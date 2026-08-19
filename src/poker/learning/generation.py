import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from poker.agents import (
	CallingStationAgent,
	ExpertAgent,
	NitAgent,
	RandomAgent,
	ManiacAgent,
	TAGAgent,
	LAGAgent,
)
from poker.arena.runner import ArenaRunner
from poker.learning.dataset import (
	LearningDatasetAnalyzer,
	LearningDatasetCapture,
	LearningDatasetWriter,
)


@dataclass(frozen=True)
class DatasetGenerationConfig:
	hands: int
	seed: int = 42
	starting_stack: int = 100
	validation_fraction: float = 0.1
	profile_scope: str = "global"
	agents: tuple[str, ...] = ("expert", "calling_station", "nit")
	teacher: str | None = "expert"
	expert_equity_samples: int = 300

	def validate(self):
		if self.hands <= 0:
			raise ValueError("hands must be positive")
		if self.starting_stack <= 0:
			raise ValueError("starting_stack must be positive")
		if not 0.0 < self.validation_fraction < 1.0:
			raise ValueError("validation_fraction must be between 0 and 1")
		if len(self.agents) < 2:
			raise ValueError("dataset generation requires at least two agents")
		if len(set(self.agents)) != len(self.agents):
			raise ValueError("agent specs must be unique")
		if self.teacher is not None and self.teacher not in self.agents:
			raise ValueError("teacher must be one of the configured agents")
		if self.expert_equity_samples <= 0:
			raise ValueError("expert_equity_samples must be positive")
		if self.profile_scope != "global":
			raise ValueError(
				"standalone dataset generation currently supports profile_scope='global'"
			)


@dataclass(frozen=True)
class DatasetGenerationResult:
	raw_path: Path
	train_path: Path
	validation_path: Path
	manifest_path: Path
	raw_samples: int
	train_samples: int
	validation_samples: int
	arena_hands: int
	arena_failed_hands: int


class LearningDatasetGenerator:
	def __init__(self, analyzer=None):
		self.analyzer = analyzer or LearningDatasetAnalyzer()

	def generate(self, output_dir, config):
		config.validate()
		output_dir = Path(output_dir)
		output_dir.mkdir(parents=True, exist_ok=True)

		raw_path = output_dir / "dataset.jsonl"
		train_path = output_dir / "train.jsonl"
		validation_path = output_dir / "validation.jsonl"
		manifest_path = output_dir / "manifest.json"

		for path in (raw_path, train_path, validation_path, manifest_path):
			if path.exists():
				path.unlink()

		agents = self._build_agents(
			config.agents,
			config.seed,
			config.expert_equity_samples,
		)
		capture = LearningDatasetCapture(
			LearningDatasetWriter(raw_path),
			profile_scope=config.profile_scope,
			include_players=(
				(config.teacher,)
				if config.teacher is not None
				else None
			),
		)
		stats = ArenaRunner(
			agents,
			starting_stack=config.starting_stack,
			decision_observer=capture,
		).run(
			hands=config.hands,
			seed=config.seed,
		)

		if stats.failed_hands:
			raise RuntimeError(
				f"Dataset generation encountered {stats.failed_hands} failed hands"
			)

		raw_summary = self.analyzer.analyze(raw_path)
		train_samples, validation_samples = self._split(
			raw_path,
			train_path,
			validation_path,
			config.validation_fraction,
			config.seed,
		)
		train_summary = self.analyzer.analyze(train_path)
		validation_summary = self.analyzer.analyze(validation_path)

		manifest = {
			"config": {
				**asdict(config),
				"agents": list(config.agents),
			},
			"arena": {
				"hands": stats.hands,
				"failed_hands": stats.failed_hands,
			},
			"raw": raw_summary,
			"train": train_summary,
			"validation": validation_summary,
		}
		manifest_path.write_text(
			json.dumps(
				manifest,
				indent=2,
				ensure_ascii=False,
				sort_keys=True,
			)
			+ "\n",
			encoding="utf-8",
		)

		return DatasetGenerationResult(
			raw_path=raw_path,
			train_path=train_path,
			validation_path=validation_path,
			manifest_path=manifest_path,
			raw_samples=capture.samples_written,
			train_samples=train_samples,
			validation_samples=validation_samples,
			arena_hands=stats.hands,
			arena_failed_hands=stats.failed_hands,
		)

	def _build_agents(self, specs, seed, expert_equity_samples):
		agents = {}
		for index, spec in enumerate(specs):
			if spec == "random":
				agent = RandomAgent(seed=seed + 100000 + index)
			elif spec == "expert":
				agent = ExpertAgent(
					seed=seed + 200000 + index,
					equity_samples=expert_equity_samples,
				)
			elif spec == "calling_station":
				agent = CallingStationAgent()
			elif spec == "nit":
				agent = NitAgent()
			elif spec == "maniac":
				agent = ManiacAgent(seed=seed + 300000 + index)
			elif spec == "tag":
				agent = TAGAgent(seed=seed + 400000 + index)
			elif spec == "lag":
				agent = LAGAgent(seed=seed + 500000 + index)
			else:
				raise ValueError(f"Unsupported dataset agent: {spec}")

			agents[spec] = agent

		return agents

	def _split(
		self,
		raw_path,
		train_path,
		validation_path,
		validation_fraction,
		seed,
	):
		lines = [
			line
			for line in raw_path.read_text(encoding="utf-8").splitlines()
			if line.strip()
		]
		if len(lines) < 2:
			raise ValueError("dataset must contain at least two samples to split")

		indices = list(range(len(lines)))
		random.Random(seed).shuffle(indices)
		validation_count = max(
			1,
			min(
				len(lines) - 1,
				round(len(lines) * validation_fraction),
			),
		)
		validation_indices = set(indices[:validation_count])

		train_lines = [
			line
			for index, line in enumerate(lines)
			if index not in validation_indices
		]
		validation_lines = [
			line
			for index, line in enumerate(lines)
			if index in validation_indices
		]

		self._write_lines(train_path, train_lines)
		self._write_lines(validation_path, validation_lines)

		return len(train_lines), len(validation_lines)

	def _write_lines(self, path, lines):
		path.write_text(
			"\n".join(lines) + "\n",
			encoding="utf-8",
		)
