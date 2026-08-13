import json

from poker.learning.generation import (
	DatasetGenerationConfig,
	LearningDatasetGenerator,
)


def test_dataset_generator_is_reproducible_and_writes_split_manifest(tmp_path):
	config = DatasetGenerationConfig(
		hands=30,
		seed=123,
		validation_fraction=0.2,
		agents=("random", "calling_station", "nit"),
	)
	generator = LearningDatasetGenerator()

	first = generator.generate(tmp_path / "first", config)
	second = generator.generate(tmp_path / "second", config)

	assert first.raw_samples > 0
	assert first.raw_samples == first.train_samples + first.validation_samples
	assert first.arena_failed_hands == 0
	assert first.raw_path.read_bytes() == second.raw_path.read_bytes()
	assert first.train_path.read_bytes() == second.train_path.read_bytes()
	assert (
		first.validation_path.read_bytes()
		== second.validation_path.read_bytes()
	)

	manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
	assert manifest["config"]["seed"] == 123
	assert manifest["config"]["agents"] == [
		"random",
		"calling_station",
		"nit",
	]
	assert manifest["raw"]["samples"] == first.raw_samples
	assert manifest["train"]["samples"] == first.train_samples
	assert manifest["validation"]["samples"] == first.validation_samples
	assert manifest["raw"]["consistent_observation_size"] is True
	assert manifest["raw"]["consistent_action_mask_size"] is True
	assert manifest["raw"]["consistent_action_sizing_size"] is True


def test_dataset_generator_rejects_invalid_configuration(tmp_path):
	generator = LearningDatasetGenerator()

	for config, expected in (
		(
			DatasetGenerationConfig(hands=0),
			"hands must be positive",
		),
		(
			DatasetGenerationConfig(
				hands=10,
				validation_fraction=1.0,
			),
			"validation_fraction",
		),
		(
			DatasetGenerationConfig(
				hands=10,
				agents=("nit", "nit"),
			),
			"agent specs must be unique",
		),
		(
			DatasetGenerationConfig(
				hands=10,
				profile_scope="private",
			),
			"profile_scope='global'",
		),
	):
		try:
			generator.generate(tmp_path / "invalid", config)
		except ValueError as error:
			assert expected in str(error)
		else:
			raise AssertionError("Expected dataset configuration validation")
