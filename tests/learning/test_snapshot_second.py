from copy import deepcopy

import pytest
import torch
from torch.utils.data import DataLoader

from poker.learning import snapshot_dataset as dataset
from poker.learning import snapshot_training as training
from poker.learning.advisor_contract import ACTIONS
from poker.learning.snapshot_actions import target
from poker.learning.snapshot_encoding import encode
from poker.learning.snapshot_metrics import PolicyMetrics
from poker.learning.snapshot_model import SnapshotPolicy
from tests.learning.test_snapshot_policy import sample


def sized_row():
    observation = sample()
    action = next(a for a in ("raise", "bet") if observation.legal["actions"][a])
    low, high = (observation.legal[action + "_to_" + b] for b in ("min", "max"))
    index, fraction, sizing = target(observation, action, (low + high) // 2)
    return {
        "observation": observation,
        "encoded": encode(observation),
        "action_index": index,
        "sizing_fraction": fraction,
        "sizing_mask": sizing,
    }


def loss_batch(extra_passive=0, *, span=99):
    n = extra_passive + 1
    batch = {
        "action_index": torch.zeros(n, dtype=torch.long),
        "sizing_target": torch.tensor([9 / span] + [0.0] * extra_passive),
        "sizing_mask": torch.tensor([True] + [False] * extra_passive),
        "sizing_min_bb": torch.tensor([1.0] * n),
        "sizing_span_bb": torch.tensor([float(span)] * n),
    }
    outputs = {
        "action_logits": torch.zeros(n, 6, requires_grad=True),
        "sizing_fraction": torch.tensor([19 / span] * n, requires_grad=True),
    }
    return outputs, batch


def test_sizing_loss_is_not_diluted_by_passive_rows_and_uses_actual_amounts():
    values = []
    for passive, span in ((0, 99), (15, 99), (0, 199)):
        output, batch = loss_batch(passive, span=span)
        loss = training.loss_terms(
            output, batch, objective="balanced-bb-v2", class_weights=torch.ones(6)
        )[2]
        values.append(loss.item())
        gradient = torch.autograd.grad(loss, output["sizing_fraction"])[0]
        assert gradient[0] > 0  # Overbet must be pulled down.
        assert torch.count_nonzero(gradient[1:]) == 0
    assert values == pytest.approx([values[0]] * 3)


@pytest.mark.parametrize("fixed", [False, True])
def test_empty_or_fixed_sizing_targets_have_zero_loss_and_finite_gradient(fixed):
    output, batch = loss_batch()
    if fixed:
        batch["sizing_span_bb"][:] = 0
    else:
        batch["sizing_mask"][:] = False
    loss = training.loss_terms(
        output, batch, objective="balanced-bb-v2", class_weights=torch.ones(6)
    )[2]
    assert loss.item() == 0
    assert torch.equal(torch.autograd.grad(loss, output["sizing_fraction"])[0], torch.zeros(1))


def test_class_weights_promote_rare_train_labels_without_zeroing_unseen_labels():
    rows = [{"action_index": 0}] * 100 + [{"action_index": 4}] * 4
    weights = training.train_class_weights(rows)
    assert weights[4] > weights[0] > 0
    assert weights[5] == 1
    assert sum(float(weights[r["action_index"]]) for r in rows) / len(rows) == pytest.approx(1)
    with pytest.raises(ValueError, match="class weights"):
        training.loss_terms(*loss_batch(), objective="balanced-bb-v2")


def test_epoch_metrics_ignore_batch_partition_and_do_not_update_weights():
    row = sized_row()
    passive = {
        **row,
        "action_index": ACTIONS.index("fold"),
        "sizing_mask": False,
        "sizing_fraction": 0.0,
    }
    rows = [row, passive, passive, row, passive]
    model = SnapshotPolicy(seat_width=8, hidden_width=16)
    before = deepcopy(model.state_dict())
    weights = training.train_class_weights(rows)
    reports = [
        training.epoch(
            model,
            DataLoader(rows, batch_size=n, collate_fn=training.collate),
            "cpu",
            objective="balanced-bb-v2",
            class_weights=weights,
        )
        for n in (2, 5)
    ]
    for key in ("loss", "action_loss", "sizing_loss", "correct"):
        assert reports[0][key] == pytest.approx(reports[1][key], rel=1e-5)
    assert reports[0]["sizing_denominator"] == 2
    assert all(torch.equal(before[k], v) for k, v in model.state_dict().items())


def test_metrics_separate_missed_actions_from_conditional_sizes():
    row = sized_row()
    metrics = PolicyMetrics()
    detail = metrics.add(row, ACTIONS.index("fold"), row["sizing_fraction"])
    report = metrics.report()
    action = ACTIONS[row["action_index"]]
    assert report["per_action"][action]["recall"] == 0
    assert report["per_action"]["all_in"]["recall"] is None
    assert detail["absolute_error_bb"] == 0
    assert report["sizing"]["conditional_mae_bb"] == 0
    assert report["sizing"]["matching_actions_mae_bb"] is None


def test_parallel_generation_matches_serial_and_focus_stays_in_train(tmp_path):
    kwargs = dict(hands=60, extra_train_hands=20, seed=71000, equity_samples=1)
    serial = dataset.prepare(tmp_path / "serial", workers=1, **kwargs)
    parallel = dataset.prepare(tmp_path / "parallel", workers=2, **kwargs)
    assert serial["split_sha256"] == parallel["split_sha256"]
    assigned = parallel["assigned_seeds"]
    assert set(range(71060, 71080)) <= set(assigned["train"])
    assert max(assigned["validation"] + assigned["test"]) < 71060
    data, _ = dataset.load_dataset(tmp_path / "parallel")
    assert all(
        2 <= len(row["observation"].players) <= 3
        for row in data["train"]
        if int(row["observation"].hand_id.split(":")[1]) >= 71060
    )


def test_generator_refuses_manifest_when_sources_change(tmp_path, monkeypatch):
    import poker.agents
    from tests.learning.test_advisor_contract import Caller

    monkeypatch.setattr(poker.agents, "ExpertAgent", lambda **kwargs: Caller())
    calls = iter(({"code": "before"}, {"code": "after"}))
    monkeypatch.setattr(dataset, "source_hashes", lambda: next(calls))
    with pytest.raises(ValueError, match="Source files changed"):
        dataset.prepare(tmp_path, hands=30, seed=71800, equity_samples=1)
    assert not (tmp_path / "manifest.json").exists()


@pytest.mark.parametrize(
    "cards,selected",
    [
        (["10♠", "10♦"], True),
        (["A♣", "K♥"], True),
        (["A♥", "Q♥"], True),
        (["9♠", "9♦"], False),
        (["A♥", "Q♦"], False),
        (["K♠", "J♠"], False),
    ],
)
def test_focus_selection_uses_only_hero_cards(cards, selected):
    assert dataset.focus_hero_cards(cards) is selected


def test_focused_labels_reproduce_probe_without_changing_teacher(monkeypatch):
    # These probe seeds precede the final experiment; no held-out final seeds are used.
    labels = {}
    compared = False
    for seed in range(151000, 151150):
        rows, rejected = dataset.generate_hand((seed, 8, True))
        if rows and not compared:
            with monkeypatch.context() as context:
                context.setattr(dataset, "focus_hero_cards", lambda cards: True)
                assert dataset.generate_hand((seed, 8, True)) == (rows, rejected)
            compared = True
        for row in rows:
            cards = row["observation"]["hero_cards"]
            ranks = sorted("23456789TJQKA".index(card[0]) for card in cards)
            assert (
                (ranks[0] == ranks[1] and ranks[0] >= 8)
                or ranks == [11, 12]
                or (ranks == [10, 12] and cards[0][1] == cards[1][1])
            )
            labels[row["target"]["action"]] = labels.get(row["target"]["action"], 0) + 1
    assert labels.get("raise", 0) > 0
    assert compared
