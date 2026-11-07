from copy import deepcopy
from dataclasses import replace
from itertools import permutations

import pytest
import torch

from poker.learning import snapshot_training as training
from poker.learning.snapshot_dataset import load_dataset
from poker.learning.snapshot_encoding import (
    LAYOUT_SHA256,
    TABLE_FEATURES,
    encode,
    layout_for,
    layout_hash,
)
from poker.learning.snapshot_model import SnapshotPolicy, batch_tensors, checkpoint, load_checkpoint
from poker.learning.snapshot_symmetry import permute_encoded
from tests.learning.test_snapshot_dataset import write_dataset
from tests.learning.test_snapshot_policy import sample


def test_raw_v1_layout_remains_exact_and_v2_only_adds_public_card_facts():
    assert LAYOUT_SHA256 == "9dc4e504ba4923dd9c7b2f0941a073b8a5d417184a366ac80871165a3cd50d30"
    obs = sample()
    obs.street, obs.board, obs.hero_cards = "turn", ["6h", "7h", "Qc", "2d"], ["8h", "9h"]
    raw, extra = encode(obs), encode(obs, feature_set="cards-v2")
    assert extra.table[: len(TABLE_FEATURES)] == raw.table
    assert extra.players == raw.players and extra.action_mask == raw.action_mask
    assert extra.seat_mask == raw.seat_mask
    assert extra.encoding == "snapshot-features/2" and extra.layout_sha256 != raw.layout_sha256
    for order in permutations(range(4)):
        changed = deepcopy(obs)
        changed.hero_cards = [c[0] + "cdhs"[order["cdhs".index(c[1])]] for c in obs.hero_cards]
        changed.board = [c[0] + "cdhs"[order["cdhs".index(c[1])]] for c in obs.board]
        assert encode(changed, feature_set="cards-v2") == permute_encoded(extra, order)
    obs.history = [{"hole_cards": ["As", "Ac"], "target": "raise"}]
    obs.evidence = {"future_board": ["Ah"], "equity": 0.99}
    for player in obs.players:
        player.name, player.statistics = "hidden_label", {"target": "raise"}
    assert encode(obs, feature_set="cards-v2").table == extra.table
    with pytest.raises(ValueError, match="incompatible"):
        batch_tensors([raw, extra])
    with pytest.raises(ValueError, match="width"):
        batch_tensors([replace(extra, table=raw.table)])


@pytest.mark.parametrize("features", ["raw-v1", "cards-v2"])
def test_both_checkpoint_versions_round_trip_and_reject_crossed_metadata(tmp_path, features):
    model = SnapshotPolicy(seat_width=8, hidden_width=16, feature_set=features).eval()
    original = checkpoint(model)
    path = tmp_path / "unit_untrained.pt"
    torch.save(original, path)
    restored = load_checkpoint(path)
    assert restored.feature_set == features
    batch = batch_tensors([encode(sample(), feature_set=features)])
    with torch.no_grad():
        expected, actual = model(**batch), restored(**batch)
        assert all(torch.equal(expected[k], actual[k]) for k in expected)
    other = "cards-v2" if features == "raw-v1" else "raw-v1"
    with pytest.raises(ValueError, match="shapes"):
        model(**batch_tensors([encode(sample(), feature_set=other)]))
    corrupted = deepcopy(original)
    corrupted["encoding"] = layout_for(other)["encoding"]
    corrupted["layout_sha256"] = layout_hash(other)
    torch.save(corrupted, path)
    with pytest.raises(ValueError, match="layout"):
        load_checkpoint(path)


def test_v2_data_loading_preflight_and_evaluation_use_checkpoint_features(tmp_path, monkeypatch):
    directory = write_dataset(tmp_path / "data")
    raw, manifest = load_dataset(directory)
    enhanced, new_manifest = load_dataset(directory, feature_set="cards-v2")
    assert manifest == new_manifest
    for split in raw:
        for a, b in zip(raw[split], enhanced[split], strict=True):
            assert a["observation"].to_dict() == b["observation"].to_dict()
            assert a["action_index"] == b["action_index"]
            assert a["sizing_fraction"] == b["sizing_fraction"]

    def forbidden(*args, **kwargs):
        raise AssertionError("This check must not create an optimizer")

    monkeypatch.setattr(torch.optim, "AdamW", forbidden)
    report = training.preflight(directory, feature_set="cards-v2")
    assert report["input_encoding"] == "snapshot-features/2" and not report["policy_called"]
    model = SnapshotPolicy(seat_width=8, hidden_width=16, feature_set="cards-v2")
    weights = tmp_path / "unit_untrained.pt"
    torch.save(checkpoint(model), weights)
    evaluated = training.evaluate(directory, weights, tmp_path / "evaluation")
    assert evaluated["input_layout_sha256"] == layout_hash("cards-v2")
    assert not evaluated["training_run"]
    batch = training.collate(enhanced["train"], suit_generator=torch.Generator().manual_seed(42))
    before = deepcopy(model.state_dict())
    outputs = model(**{key: batch[key] for key in ("table", "players", "seat_mask", "action_mask")})
    loss = training.loss_terms(
        outputs,
        batch,
        objective="balanced-bb-v2",
        class_weights=training.train_class_weights(enhanced["train"]),
    )[0]
    gradients = torch.autograd.grad(loss, tuple(model.parameters()), allow_unused=True)
    assert all(torch.isfinite(g).all() for g in gradients if g is not None)
    assert all(torch.equal(before[key], value) for key, value in model.state_dict().items())
