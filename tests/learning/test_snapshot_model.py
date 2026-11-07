import pytest
import torch

from poker.learning.snapshot_encoding import encode
from poker.learning.snapshot_model import SnapshotPolicy, batch_tensors, checkpoint, load_checkpoint
from tests.learning.test_snapshot_policy import sample


def test_model_masks_illegal_actions_and_padding_without_training():
    model = SnapshotPolicy(seat_width=8, hidden_width=16).eval()
    batch = batch_tensors([encode(sample())])
    with torch.no_grad():
        before = model(**batch)
        batch["players"][:, 2:] = 10
        after = model(**batch)
    assert torch.equal(before["action_logits"], after["action_logits"])
    assert torch.equal(before["sizing_fraction"], after["sizing_fraction"])
    assert torch.isneginf(before["action_logits"][batch["action_mask"] == 0]).all()
    assert torch.isfinite(before["action_logits"][batch["action_mask"] == 1]).all()
    assert ((before["sizing_fraction"] >= 0) & (before["sizing_fraction"] <= 1)).all()


@pytest.mark.parametrize("damage", ["no_actions", "no_hero", "nan", "shape", "nonbinary"])
def test_model_refuses_invalid_batches(damage):
    model, batch = SnapshotPolicy(), batch_tensors([encode(sample())])
    if damage == "no_actions":
        batch["action_mask"][:] = 0
    elif damage == "no_hero":
        batch["seat_mask"][:, 0] = 0
    elif damage == "nan":
        batch["table"][0, 0] = float("nan")
    elif damage == "shape":
        batch["players"] = batch["players"][:, :2]
    else:
        batch["action_mask"][0, 0] = 0.5
    with pytest.raises(ValueError):
        model(**batch)


def test_checkpoint_round_trip_and_rejection_of_legacy_or_changed_layout(tmp_path):
    model = SnapshotPolicy(seat_width=8, hidden_width=16).eval()
    path = tmp_path / "untrained_test_only.pt"
    data = checkpoint(model)
    torch.save(data, path)
    restored = load_checkpoint(path)
    batch = batch_tensors([encode(sample())])
    with torch.no_grad():
        assert torch.equal(model(**batch)["action_logits"], restored(**batch)["action_logits"])
    data["layout_sha256"] = "incompatible"
    torch.save(data, path)
    with pytest.raises(ValueError):
        load_checkpoint(path)
    torch.save(model.state_dict(), path)
    with pytest.raises(ValueError):
        load_checkpoint(path)
