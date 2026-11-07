from copy import deepcopy

import pytest
import torch

from poker.learning import snapshot_dataset as dataset
from poker.learning import snapshot_holdout as holdout
from poker.learning import snapshot_training as training
from tests.learning.test_advisor_contract import Caller
from tests.learning.test_snapshot_second import sized_row


def rows():
    row = sized_row()
    return [deepcopy(row) for _ in range(16)]


def test_augmentation_changes_only_card_inputs_without_mutating_dataset():
    data = rows()
    before = deepcopy(data)
    original = training.collate(data)
    augmented = training.collate(data, suit_generator=torch.Generator().manual_seed(175))
    assert not torch.equal(original["table"][:, 4:108], augmented["table"][:, 4:108])
    for key in original.keys() - {"table"}:
        assert torch.equal(original[key], augmented[key])
    assert torch.equal(original["table"][:, :4], augmented["table"][:, :4])
    assert torch.equal(original["table"][:, 108:], augmented["table"][:, 108:])
    assert all(
        a["encoded"] == b["encoded"] and a["observation"].to_dict() == b["observation"].to_dict()
        for a, b in zip(data, before, strict=True)
    )


def test_train_augmentation_reproducible_across_epochs_validation_unchanged():
    data = {"train": rows(), "validation": rows()}
    loaders = [
        training.training_loaders(data, batch_size=5, seed=42, augmentation="suit-permutation-v1")
        for _ in range(2)
    ]
    baseline = training.training_loaders(data, batch_size=5, seed=42)
    epoch_cards = []
    for _ in range(2):
        first, second, raw = (
            list(loaders[0]["train"]),
            list(loaders[1]["train"]),
            list(baseline["train"]),
        )
        for a, b, c in zip(first, second, raw, strict=True):
            assert all(torch.equal(a[key], b[key]) for key in a)
            assert all(torch.equal(a[key], c[key]) for key in a if key != "table")
        epoch_cards.append(torch.cat([b["table"] for b in first]))
    assert not torch.equal(*epoch_cards)
    for a, b in zip(loaders[0]["validation"], baseline["validation"], strict=True):
        assert all(torch.equal(a[key], b[key]) for key in a)
    assert "test" not in loaders[0]


def test_suit_rng_does_not_change_shuffle_or_global_model_initialization_rng():
    data = rows()
    for i, row in enumerate(data):
        # Different targets identify order; numerical card transformation never sees labels.
        row["sizing_fraction"] = i / len(data)
    inputs = {"train": data, "validation": data}
    initial_rng = torch.random.get_rng_state().clone()
    augmented = training.training_loaders(
        inputs, batch_size=4, seed=217, augmentation="suit-permutation-v1"
    )
    baseline = training.training_loaders(inputs, batch_size=4, seed=217)
    for _ in range(2):
        for a, b in zip(augmented["train"], baseline["train"], strict=True):
            assert torch.equal(a["sizing_target"], b["sizing_target"])
    assert torch.equal(initial_rng, torch.random.get_rng_state())
    with pytest.raises(ValueError, match="augmentation"):
        training.training_loaders(inputs, batch_size=4, seed=217, augmentation="bad")


@pytest.fixture
def parent_dataset(tmp_path, monkeypatch):
    import poker.agents

    monkeypatch.setattr(poker.agents, "ExpertAgent", lambda **kw: Caller())
    source = tmp_path / "source"
    dataset.prepare(source, hands=30, seed=71800, equity_samples=1)
    return source


def test_holdout_keeps_train_validation_exact_and_assigns_all_fresh_seeds(parent_dataset, tmp_path):
    output = tmp_path / "fresh"
    report = holdout.prepare_holdout(parent_dataset, output, hands=30, seed=72100, workers=1)
    data, _ = dataset.load_dataset(output)
    for name in ("train", "validation"):
        assert (parent_dataset / f"{name}.jsonl").read_bytes() == (
            output / f"{name}.jsonl"
        ).read_bytes()
    assert report["assigned_seeds"]["test"] == list(range(72100, 72130))
    assert all(
        72100 <= int(row["observation"].hand_id.split(":")[1]) < 72130 for row in data["test"]
    )
    assert not report["training_run"] and not report["player_db_written"]
    with pytest.raises(ValueError, match="empty output"):
        holdout.prepare_holdout(parent_dataset, output, hands=30, seed=72100, workers=1)


def test_holdout_rejects_overlap_including_assigned_hands_without_records(parent_dataset, tmp_path):
    with pytest.raises(ValueError, match="overlap"):
        holdout.prepare_holdout(
            parent_dataset, tmp_path / "overlap", hands=30, seed=71790, workers=1
        )
    other = tmp_path / "other"
    dataset.prepare(other, hands=30, seed=71900, equity_samples=1)
    with pytest.raises(ValueError, match="overlap"):
        holdout.prepare_holdout(
            parent_dataset, tmp_path / "overlap2", hands=30, seed=71929, workers=1, exclude=[other]
        )
    assert not (tmp_path / "overlap").exists()
    assert not (tmp_path / "overlap2").exists()


def test_holdout_does_not_publish_manifest_after_source_change(
    parent_dataset, tmp_path, monkeypatch
):
    versions = iter([{"source": "old"}, {"source": "new"}])
    monkeypatch.setattr(holdout, "source_hashes", lambda: next(versions))
    output = tmp_path / "changed"
    with pytest.raises(ValueError, match="Source files changed"):
        holdout.prepare_holdout(parent_dataset, output, hands=30, seed=72100, workers=1)
    assert not (output / "manifest.json").exists()
