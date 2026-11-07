from copy import deepcopy
from dataclasses import replace
from itertools import permutations

import pytest

from poker.agents.expert import ExpertAgent
from poker.learning.snapshot_dataset import generate_hand
from poker.learning.snapshot_diagnostics import CachedRanges, permute_encoded, recheck, replay_cases
from poker.learning.snapshot_encoding import encode
from tests.learning.test_advisor_contract import Caller
from tests.learning.test_snapshot_policy import sample


def public_states(monkeypatch):
    import poker.agents

    monkeypatch.setattr(poker.agents, "ExpertAgent", lambda **kw: Caller())
    captured = []
    rows, rejected = generate_hand(
        (71800, 1, False), decision_observer=lambda *args: captured.append(args)
    )
    assert captured
    return rows, rejected, captured


def test_callback_cannot_mutate_saved_sample_or_alter_trajectory(monkeypatch):
    rows, rejected, captured = public_states(monkeypatch)

    def callback(state, legal, decision, record):
        record["target"]["action"] = "corrupted"
        record["observation"]["players"].clear()

    assert generate_hand((71800, 1, False), decision_observer=callback) == (rows, rejected)
    assert generate_hand((71800, 1, False)) == (rows, rejected)
    assert all(
        not hasattr(player, "hole_cards") for state, *_ in captured for player in state.players
    )


def test_all_suit_permutations_match_reencoding_and_preserve_other_information():
    observation = sample()
    observation.street, observation.board = "flop", ["2c", "3d", "4h"]
    observation.hero_cards = ["As", "Ah"]
    encoded = encode(observation)
    for order in permutations(range(4)):
        changed = deepcopy(observation)
        mapping = dict(zip("cdhs", ("cdhs"[i] for i in order), strict=True))
        changed.hero_cards = [c[0] + mapping[c[1]] for c in observation.hero_cards]
        changed.board = [c[0] + mapping[c[1]] for c in observation.board]
        assert permute_encoded(encoded, order) == encode(changed)
        inverse = tuple(order.index(i) for i in range(4))
        assert permute_encoded(permute_encoded(encoded, order), inverse) == encoded
    with pytest.raises(ValueError, match="permutation"):
        permute_encoded(encoded, (0, 0, 1, 2))


def test_cached_ranges_preserve_exact_monte_carlo_and_teacher_rules(monkeypatch):
    _, _, captured = public_states(monkeypatch)
    state, legal, _, _ = captured[0]
    original = ExpertAgent(seed=871, equity_samples=3)
    cached = ExpertAgent(seed=871, equity_samples=3, range_model=CachedRanges())
    assert original.equity.estimate(state) == cached.equity.estimate(state)
    expected = ExpertAgent(seed=871, equity_samples=3).choose_action(state, legal)
    actual = recheck(state, legal, samples=3, seeds=[871])[0]
    assert actual["action"] == expected.action.value
    assert actual["amount_to"] == (
        expected.amount if expected.action.value in ("bet", "raise") else None
    )
    assert original.equity.random.getstate() == cached.equity.random.getstate()
    assert recheck(state, legal, samples=3, seeds=[871])[0] == actual


def test_replay_rejects_changed_trajectory_before_rechecking(monkeypatch):
    import poker.learning.snapshot_diagnostics as diagnostics

    rows, _, captured = public_states(monkeypatch)
    selected = {rows[0]["observation"]["observation_id"]: {"action": "raise"}}
    calls = []
    monkeypatch.setattr(
        diagnostics, "recheck", lambda state, legal, **kw: calls.append(state) or []
    )
    result = replay_cases((71800, rows, selected, 3, 1, 1))
    assert len(result) == 1 and result[0]["original_trajectory_exact"]
    assert calls == [captured[0][0], replace(captured[0][0], action_history=())]
    wrong = deepcopy(rows)
    wrong[0]["target"]["action"] = "changed"
    calls.clear()
    with pytest.raises(ValueError, match="did not reproduce"):
        replay_cases((71800, wrong, selected, 3, 1, 1))
    assert calls == []
