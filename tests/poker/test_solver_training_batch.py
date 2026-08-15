from dataclasses import dataclass

import pytest

from poker.solver.training_batch import (
	SolverTrainingBatch,
	build_solver_training_batch,
)


LEGAL_MASK = (1.0, 0.0, 1.0, 0.0, 1.0, 1.0)


@dataclass(frozen=True)
class Sample:
	observation: tuple[float, ...]
	probabilities: tuple[float, ...]
	legal_mask: tuple[float, ...] = LEGAL_MASK


def test_solver_training_batch_contract_preserves_arrays():
	batch = build_solver_training_batch(
		[
			Sample(
				(1.0, 2.0),
				(0.1, 0.0, 0.2, 0.0, 0.6, 0.1),
			),
		]
	)

	assert batch.size == 1
	assert batch.observations == ((1.0, 2.0),)
	assert batch.probabilities == (
		(0.1, 0.0, 0.2, 0.0, 0.6, 0.1),
	)
	assert batch.legal_masks == (LEGAL_MASK,)


def test_solver_training_batch_rejects_empty_batch():
	with pytest.raises(
		ValueError,
		match="training batch must not be empty",
	):
		build_solver_training_batch([])


def test_solver_training_batch_rejects_inconsistent_observation_sizes():
	with pytest.raises(
		ValueError,
		match="batch observations must have consistent sizes",
	):
		build_solver_training_batch(
			[
				Sample(
					(1.0, 2.0),
					(0.1, 0.0, 0.2, 0.0, 0.6, 0.1),
				),
				Sample(
					(3.0,),
					(0.1, 0.0, 0.2, 0.0, 0.6, 0.1),
				),
			]
		)


def test_solver_training_batch_rejects_invalid_probability_shape():
	with pytest.raises(
		ValueError,
		match="training probabilities must contain six actions",
	):
		build_solver_training_batch(
			[
				Sample((1.0, 2.0), (0.5, 0.5)),
			]
		)


def test_solver_training_batch_rejects_invalid_legal_mask_shape():
	with pytest.raises(
		ValueError,
		match="training legal masks must contain six actions",
	):
		build_solver_training_batch(
			[
				Sample(
					(1.0, 2.0),
					(1.0, 0.0, 0.0, 0.0, 0.0, 0.0),
					(1.0, 0.0),
				),
			]
		)


def test_solver_training_batch_rejects_negative_probabilities():
	with pytest.raises(
		ValueError,
		match="training probabilities cannot contain negative values",
	):
		build_solver_training_batch(
			[
				Sample(
					(1.0, 2.0),
					(0.2, 0.0, -0.1, 0.0, 0.8, 0.1),
				),
			]
		)


def test_solver_training_batch_rejects_probability_on_illegal_action():
	with pytest.raises(
		ValueError,
		match="training probability assigned to illegal action",
	):
		build_solver_training_batch(
			[
				Sample(
					(1.0, 2.0),
					(0.1, 0.1, 0.2, 0.0, 0.5, 0.1),
				),
			]
		)


def test_solver_training_batch_rejects_non_normalized_probabilities():
	batch = SolverTrainingBatch(
		observations=((1.0, 2.0),),
		probabilities=((0.2, 0.0, 0.2, 0.0, 0.2, 0.0),),
		legal_masks=(LEGAL_MASK,),
	)

	with pytest.raises(
		ValueError,
		match="training probabilities must sum to one",
	):
		batch.validate()
