from copy import deepcopy

import pytest

from poker.agents import CallingStationAgent
from poker.api import ActionDecision, play_hand
from poker.api.hand_state import build_hand_state_view, get_legal_actions
from poker.game.actions import PlayerAction
from poker.game.dealer import Dealer
from poker.game.hand_controller import HandController
from poker.game.hand_history import HandHistory, HandHistoryStore
from poker.game.hand_replay import HandReplayVerifier
from poker.learning.snapshot_contract import RULESET, SnapshotRejected, from_public_state
from poker.statistics.hand_adapter import HandStatisticsAdapter
from tests.engine.test_hand_controller import make_state


@pytest.mark.parametrize("count", [2, 3, 6, 7])
@pytest.mark.parametrize("ante", [6, 8, 10])
def test_forced_post_starts_on_flop_without_live_wager_or_blinds(count, ante):
    state = make_state(count)
    controller = HandController(Dealer(seed=901), bomb_pot_ante=ante)
    controller.start_hand(state)
    view = build_hand_state_view(state, controller)
    legal = get_legal_actions(state, controller)
    assert view.street == "flop" and len(view.board) == 3
    assert view.pot == count * ante and view.target_bet == 0
    assert view.forced_ante == ante and view.hand_variant == "bomb-pot-single-board/1"
    assert view.action_history == ()
    assert all(p.current_bet == 0 and p.total_contribution == ante for p in view.players)
    assert all(p.chips == 100 - ante for p in view.players)
    assert view.acting_player == view.players[1].name  # left of button, including heads-up
    assert legal.call_amount == 0 and legal.min_bet == 2 and legal.max_bet == 100 - ante
    assert PlayerAction.CHECK in legal.actions and PlayerAction.RAISE not in legal.actions
    events = controller.hand_history.events
    assert [e.type for e in events] == ["bomb_pot_start", "street"]
    assert events[0].data["contributions"] == {p.name: ante for p in view.players}
    assert all(p["starting_chips"] == 100 for p in controller.hand_history.players)
    controller.process_action(state, PlayerAction.BET, 5)
    following = build_hand_state_view(state, controller)
    assert following.pot == count * ante + 5
    assert get_legal_actions(state, controller).call_amount == 5
    assert following.action_history[0].contributed == 5


@pytest.mark.parametrize("ante", [0, -1, True, 2.0, "6"])
def test_invalid_forced_post_is_rejected_before_the_hand(ante):
    with pytest.raises(ValueError, match="positive integer"):
        HandController(Dealer(seed=1), bomb_pot_ante=ante)


@pytest.mark.parametrize(
    "stacks",
    [
        {"a": 3, "b": 6},
        {"a": 1, "b": 100},
        {"a": 3, "b": 6, "c": 9},
        {"a": 3, "b": 100, "c": 100},
    ],
)
def test_short_forced_posts_allins_side_pots_and_exact_replay(stacks, tmp_path):
    observed = []
    history = play_hand(
        {p: CallingStationAgent() for p in stacks},
        seed=1103,
        starting_stacks=stacks,
        bomb_pot_ante=6,
        decision_observer=lambda view, legal, decision: observed.append(view),
    )
    assert sum(history.final_stacks.values()) == sum(stacks.values())
    assert all(chips >= 0 for chips in history.final_stacks.values())
    assert history.events[0].data["contributions"] == {p: min(6, s) for p, s in stacks.items()}
    assert all(v.street != "preflop" for v in observed)
    assert all(next(p.chips for p in v.players if p.name == v.acting_player) > 0 for v in observed)
    assert all(e.type != "blinds" for e in history.events)
    store = HandHistoryStore(tmp_path / "bomb.jsonl")
    store.append(history)
    loaded = store.load_all()[0]
    assert loaded.to_dict() == history.to_dict()
    assert HandReplayVerifier().verify(loaded).ok
    damaged = deepcopy(history)
    damaged.events[0].data["contributions"][next(iter(stacks))] += 1
    assert not HandReplayVerifier().verify(damaged).ok


def test_folds_pay_out_forced_money_without_counting_it_as_voluntary_actions():
    class Folder:
        def choose_action(self, state, legal):
            if PlayerAction.BET in legal.actions:
                return ActionDecision(PlayerAction.BET, 2)
            return ActionDecision(PlayerAction.FOLD)

    history = play_hand({str(i): Folder() for i in range(6)}, seed=4, bomb_pot_ante=8)
    assert history.result == "complete"
    assert history.events[-1].data["payout"] == 50
    assert sorted(history.final_stacks.values()) == [92, 92, 92, 92, 92, 140]
    assert [e.data["contributed"] for e in history.events if e.type == "action"] == [
        2,
        0,
        0,
        0,
        0,
        0,
    ]
    assert HandReplayVerifier().verify(history).ok
    adapter = HandStatisticsAdapter()
    with pytest.raises(ValueError, match="variant-aware"):
        adapter.process_hand(history)
    assert adapter.collector.players == {}


def test_old_model_contract_rejects_bomb_pot_even_if_producer_claims_standard_rules():
    state = make_state(6)
    controller = HandController(Dealer(seed=7), bomb_pot_ante=8)
    controller.start_hand(state)
    view = build_hand_state_view(state, controller)
    observation = from_public_state(
        view,
        get_legal_actions(state, controller),
        hand_id="bomb-test",
        observation_id="1",
        big_blind=2,
        ruleset=RULESET,
    )
    assert observation.pot == 48
    assert observation.evidence["forced_ante"] == 8
    assert observation.evidence["hand_variant"] == "bomb-pot-single-board/1"
    assert len(observation.hero_cards) == 2 and len(observation.board) == 3
    assert all(p.street_contribution == 0 and p.hand_contribution == 8 for p in observation.players)
    with pytest.raises(SnapshotRejected, match="hand_variant_unsupported"):
        observation.require_valid()


def test_unknown_bomb_start_version_or_duplicate_start_cannot_replay_as_standard():
    history = play_hand({p: CallingStationAgent() for p in "abc"}, seed=8, bomb_pot_ante=6)
    for change in ("version", "duplicate", "position"):
        data = deepcopy(history.to_dict())
        if change == "version":
            data["events"][0]["data"]["schema_version"] = "bomb-pot-start/99"
        elif change == "duplicate":
            data["events"].append(deepcopy(data["events"][0]))
        else:
            data["events"][0], data["events"][1] = data["events"][1], data["events"][0]
        result = HandReplayVerifier().verify(HandHistory.from_dict(data))
        assert not result.ok and result.mode == "invalid"
