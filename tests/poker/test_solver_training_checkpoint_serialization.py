import pytest

from poker.solver.training_checkpoint import (
	create_checkpoint,
	deserialize_checkpoint,
	serialize_checkpoint,
)


def test_training_checkpoint_json_round_trip_is_deterministic():
	checkpoint = create_checkpoint(
		10,
		{
			"epoch": 2,
			"source": "solver",
		},
	)

	payload = serialize_checkpoint(checkpoint)
	restored = deserialize_checkpoint(payload)

	assert payload == (
		'{"metadata":{"epoch":2,"source":"solver"},"step":10}'
	)
	assert restored == checkpoint


def test_training_checkpoint_serialization_rejects_wrong_type():
	with pytest.raises(TypeError, match="invalid checkpoint"):
		serialize_checkpoint({"step": 1})


def test_training_checkpoint_deserialization_rejects_extra_fields():
	with pytest.raises(
		ValueError,
		match="checkpoint payload fields are invalid",
	):
		deserialize_checkpoint(
			'{"metadata":{},"step":1,"unexpected":true}'
		)
