import json
from copy import deepcopy

import pytest
import torch

from poker.learning import snapshot_dataset as dataset
from poker.learning import snapshot_training as training
from poker.learning.snapshot_encoding import LAYOUT_SHA256
from poker.learning.snapshot_model import SnapshotPolicy
from tests.learning.test_advisor_contract import Caller
from tests.learning.test_snapshot_policy import sample


def write_dataset(directory, *, leak=False):
    directory.mkdir()
    counts = {}
    for n, name in enumerate(dataset.SPLITS):
        observation = sample()
        seed = 1 if leak else n + 1
        observation.hand_id = f"sim:{seed}"
        action = next(a for a, allowed in observation.legal["actions"].items() if allowed)
        row = {
            "schema_version": dataset.SAMPLE_VERSION,
            "deal_seed": seed,
            "observation": observation.to_dict(),
            "target": {"action": action, "amount_to": None},
            "teacher": "unit-test",
        }
        (directory / f"{name}.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
        counts[name] = 1
    manifest = {
        "schema_version": dataset.DATASET_VERSION,
        "layout_sha256": LAYOUT_SHA256,
        "config": {"unit_test_only": True},
        "teacher": "unit-test",
        "samples": counts,
        "split_sha256": {n: dataset.digest(directory / f"{n}.jsonl") for n in dataset.SPLITS},
    }
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return directory


def test_preflight_validates_all_splits_without_network_or_optimizer(tmp_path, monkeypatch):
    path = write_dataset(tmp_path / "data")

    def forbidden(*args, **kwargs):
        raise AssertionError("Preflight must not initialize a model or optimizer")

    monkeypatch.setattr(training, "SnapshotPolicy", forbidden)
    monkeypatch.setattr(torch.optim, "AdamW", forbidden)
    result = training.preflight(path)
    assert result["samples"] == {name: 1 for name in dataset.SPLITS}
    assert result["training_run"] is result["policy_called"] is False
    assert not list(tmp_path.rglob("*.pt"))


def test_split_seed_leakage_and_changed_files_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="seed leakage"):
        dataset.load_dataset(write_dataset(tmp_path / "leak", leak=True))
    path = write_dataset(tmp_path / "changed")
    with (path / "train.jsonl").open("a", encoding="utf-8") as file:
        file.write("{}\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        dataset.load_dataset(path)


def test_generation_is_reproducible_and_preserves_existing_output(tmp_path, monkeypatch):
    import poker.agents

    monkeypatch.setattr(poker.agents, "ExpertAgent", lambda **kwargs: Caller())
    a, b = tmp_path / "a", tmp_path / "b"
    first = dataset.prepare(a, hands=30, seed=71800, equity_samples=1)
    second = dataset.prepare(b, hands=30, seed=71800, equity_samples=1)
    assert first["split_sha256"] == second["split_sha256"]
    assert all(first["samples"].get(name, 0) > 0 for name in dataset.SPLITS)
    data, _ = dataset.load_dataset(a)
    assert all(r["observation"].history == [] for rows in data.values() for r in rows)
    assert any(
        p.hand_contribution is None
        for rows in data.values()
        for r in rows
        for p in r["observation"].players
    )
    with pytest.raises(ValueError, match="empty output"):
        dataset.prepare(a, hands=30, equity_samples=1)


def test_loss_masks_nonsizing_labels_and_gradients_do_not_update_weights(tmp_path):
    data, _ = dataset.load_dataset(write_dataset(tmp_path / "data"))
    batch = training.collate(data["train"])
    model = SnapshotPolicy(seat_width=8, hidden_width=16)
    before = deepcopy(model.state_dict())
    outputs = model(**{k: batch[k] for k in ("table", "players", "seat_mask", "action_mask")})
    loss, _, sizing = training.loss_terms(outputs, batch)
    assert sizing.item() == 0  # Fold target carries no sizing supervision.
    gradients = torch.autograd.grad(loss, tuple(model.parameters()), allow_unused=True)
    assert any(g is not None and torch.isfinite(g).all() and g.abs().sum() > 0 for g in gradients)
    assert all(torch.equal(before[k], v) for k, v in model.state_dict().items())


def test_nonzero_sizing_loss_and_holdout_evaluation_without_optimizer(tmp_path, monkeypatch):
    path = write_dataset(tmp_path / "data")
    data, _ = dataset.load_dataset(path)
    batch = training.collate(data["train"])
    batch["sizing_mask"][:] = True
    outputs = {"action_logits": torch.zeros(1, 6), "sizing_fraction": torch.tensor([0.75])}
    assert training.loss_terms(outputs, batch)[2].item() > 0
    model = SnapshotPolicy(seat_width=8, hidden_width=16)
    from poker.learning.snapshot_model import checkpoint

    weights = tmp_path / "untrained_unit_test.pt"
    torch.save(checkpoint(model), weights)

    def forbidden(*args, **kwargs):
        raise AssertionError("Evaluation cannot train")

    monkeypatch.setattr(torch.optim, "AdamW", forbidden)
    report = training.evaluate(path, weights, tmp_path / "eval")
    assert report["counts"]["samples"] == 1
    assert report["training_run"] is report["measures_poker_profitability"] is False
    assert (tmp_path / "eval" / "predictions.jsonl").is_file()
