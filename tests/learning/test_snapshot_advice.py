import json
from copy import deepcopy

import pytest
import torch

from poker.learning.snapshot_advice import SnapshotAdvisor, matches_observation
from poker.learning.snapshot_model import SnapshotPolicy, checkpoint
from tests.learning.test_snapshot_sizing import state
from tools.replay_snapshot_advice import replay


@pytest.fixture
def weights(tmp_path):
    path = tmp_path / "untrained_test_only.pt"
    torch.save(
        checkpoint(SnapshotPolicy(seat_width=8, hidden_width=16, feature_set="cards-v2")), path
    )
    return path


def predictable(advisor, *, bad=None):
    calls = []

    def forward(**batch):
        calls.append(batch)
        logits = torch.zeros((1, 6)).masked_fill(batch["action_mask"] == 0, float("-inf"))
        logits[0, 3] = 10
        fraction = torch.tensor([0.99])
        if bad == "logits":
            logits[0, 3] = float("nan")
        elif bad == "fraction":
            fraction[0] = 1.1
        elif bad == "unmasked":
            logits[0, 0] = 99
        return {"action_logits": logits, "sizing_fraction": fraction}

    advisor.model.forward = forward
    return calls


def test_separate_rule_keeps_action_and_logs_neural_amount_and_input_binding(weights):
    advisor = SnapshotAdvisor(weights, sizing_policy="expert-pot65-v1")
    calls = predictable(advisor)
    payload = state(pot=642, low=10, high=1842).to_dict()
    original = deepcopy(payload)
    result = advisor.advise(payload)
    assert len(calls) == 1 and result["model_called"] and result["status"] == "ready"
    assert (
        result["decision"]["action"] == result["neural_diagnostic"]["decision"]["action"] == "bet"
    )
    assert result["decision"]["amount_to"] == 417
    assert result["neural_diagnostic"]["decision"]["amount_to"] > 1800
    assert result["sizing_trace"]["policy"] == "expert-pot65-v1"
    assert matches_observation(result, payload)
    assert payload == original
    payload["observation_id"] = "later"
    assert not matches_observation(result, payload)
    payload = deepcopy(original)
    payload["pot"] += 1
    assert not matches_observation(result, payload)
    assert matches_observation(result, original)
    result["decision"]["hand_id"] = "another_hand"
    assert not matches_observation(result, original)


@pytest.mark.parametrize(
    "damage,reason",
    [
        ("turn", "not_confirmed_hero_turn"),
        ("cards", "cards_invalid"),
        ("source", "stacks_unverified"),
        ("rules", "ruleset_unverified_or_unsupported"),
        ("allin", "existing_all_in_unsupported"),
        ("shape", "malformed_snapshot"),
    ],
)
def test_blocked_state_never_calls_model_or_invents_a_decision(weights, damage, reason):
    advisor = SnapshotAdvisor(weights, sizing_policy="expert-pot65-v1")
    calls = predictable(advisor)
    payload = state().to_dict()
    if damage == "turn":
        payload["is_my_turn"] = False
    elif damage == "cards":
        payload["hero_cards"] = ["Ah", "Ah"]
    elif damage == "source":
        payload["source_blockers"] = ["stacks_unverified"]
    elif damage == "rules":
        payload["ruleset"] = None
    elif damage == "allin":
        payload["players"][0]["all_in"] = True
    else:
        payload["private_deck"] = ["As"]
    result = advisor.advise(payload)
    assert calls == [] and result["model_called"] is False
    assert result["status"] == "blocked" and reason in result["blockers"]
    assert result["decision"] is result["neural_diagnostic"] is None
    assert not matches_observation(result, payload)


@pytest.mark.parametrize("bad", ["logits", "fraction", "unmasked"])
def test_invalid_model_output_is_rejected_even_with_rule_sizing(weights, bad):
    advisor = SnapshotAdvisor(weights, sizing_policy="expert-pot65-v1")
    predictable(advisor, bad=bad)
    result = advisor.advise(state().to_dict())
    assert result["model_called"] and result["blockers"] == ["model_output_invalid"]
    assert result["decision"] is None


def test_neural_mode_and_replay_log_each_result_and_preserve_existing_outputs(weights, tmp_path):
    advisor = SnapshotAdvisor(weights, sizing_policy="neural-range-v1")
    predictable(advisor)
    payload = state().to_dict()
    result = advisor.advise(payload)
    assert result["decision"] == result["neural_diagnostic"]["decision"]
    source, output = tmp_path / "input.jsonl", tmp_path / "replay"
    stopped = {**payload, "is_my_turn": False}
    source.write_text(
        json.dumps(payload) + "\nnot-json\n" + json.dumps(stopped) + "\n", encoding="utf-8"
    )
    report = replay(source, output, weights, sizing_policy="expert-pot65-v1")
    assert report["counts"] == {"ready": 1, "model_calls": 1, "blocked": 2}
    assert not report["training_run"] and not report["hud_connected"]
    logs = [json.loads(s) for s in (output / "advice.jsonl").read_text().splitlines()]
    assert [r["source_line"] for r in logs] == [1, 2, 3]
    with pytest.raises(ValueError, match="empty"):
        replay(source, output, weights, sizing_policy="expert-pot65-v1")
    with pytest.raises(ValueError, match="explicit"):
        SnapshotAdvisor(weights, sizing_policy="auto")
