"""Variant-specific contracts cannot silently enter legacy datasets or models."""

import json
from copy import deepcopy
from dataclasses import replace

import pytest
import torch

from poker.api.hand_state import build_hand_state_view, get_legal_actions
from poker.game.dealer import Dealer
from poker.game.hand_controller import HandController
from poker.learning import snapshot_dataset as dataset
from poker.learning import snapshot_training as training
from poker.learning.snapshot_advice import SnapshotAdvisor
from poker.learning.snapshot_contract import (
    BOMB_VARIANT,
    MIXED_RULESET,
    RULESET,
    VERSION_V2,
    SnapshotRejected,
    from_dict,
    from_public_state,
)
from poker.learning.snapshot_encoding import encode, layout_for, layout_hash
from poker.learning.snapshot_model import SnapshotPolicy, batch_tensors, checkpoint, load_checkpoint
from poker.learning.snapshot_symmetry import permute_encoded
from tests.engine.test_bomb_pot import make_state
from tests.learning.test_advisor_contract import Caller


def test_cached_teacher_is_exact_for_changed_available_cards_players_and_states():
    import random

    from poker.agents.expert import ExpertAgent, full_deck, parse_card
    from poker.game.actions import PlayerAction
    from poker.strategy.ranges import PositionRangeModel

    state = make_state(4)
    controller = HandController(Dealer(seed=17), bomb_pot_ante=8)
    controller.start_hand(state)
    cached, original = dataset.CachedTeacherRanges(), PositionRangeModel()
    for _ in range(3):
        view = build_hand_state_view(state, controller)
        excluded = {parse_card(c) for c in view.hole_cards + view.board}
        cards = [c for c in full_deck() if c not in excluded]
        for player in view.players:
            for available in (cards, cards[2:], cards[1:10], cards):
                assert cached.combo_distribution(
                    available, player, view
                ) == original.combo_distribution(
                    available,
                    player,
                    view,
                )
                a, b = random.Random(714), random.Random(714)
                assert cached.sample_hole_cards(
                    available, player, view, a
                ) == original.sample_hole_cards(
                    available,
                    player,
                    view,
                    b,
                )
                assert a.getstate() == b.getstate()
        legal = get_legal_actions(state, controller)
        a = ExpertAgent(seed=87, equity_samples=16, range_model=cached)
        b = ExpertAgent(seed=87, equity_samples=16)
        assert a.choose_action(view, legal) == b.choose_action(view, legal)
        assert a.equity.random.getstate() == b.equity.random.getstate()
        action = PlayerAction.BET if PlayerAction.BET in legal.actions else PlayerAction.CALL
        controller.process_action(state, action, 2 if action == PlayerAction.BET else 0)


def test_fixed_state_diagnostic_reproduces_variant_seed():
    from poker.learning.snapshot_diagnostics import replay_cases

    for seed in range(620000, 620020):
        if not dataset.bomb_candidate(seed):
            continue
        rows, _ = dataset.generate_hand((seed, 1, False, "mixed-bomb-v1"))
        if rows:
            first = rows[0]
            cases = replay_cases(
                (
                    seed,
                    rows,
                    {first["observation"]["observation_id"]: {"action": "check"}},
                    2,
                    1,
                    1,
                    "mixed-bomb-v1",
                )
            )
            assert len(cases) == 1 and cases[0]["deal_seed"] == seed
            return
    raise AssertionError("No bomb sample in the deterministic test seeds")


def test_bomb_teacher_prior_is_uniform_before_actions_and_responds_to_postflop_bet():
    from poker.agents.expert import full_deck, parse_card
    from poker.game.actions import PlayerAction
    from poker.strategy.ranges import PositionRangeModel

    state = make_state(6)
    controller = HandController(Dealer(seed=7), bomb_pot_ante=8)
    controller.start_hand(state)
    view = build_hand_state_view(state, controller)
    player = next(p for p in view.players if p.name == view.acting_player)
    excluded = {parse_card(c) for c in view.hole_cards + view.board}
    available = [c for c in full_deck() if c not in excluded]
    model = PositionRangeModel()
    distribution = model.combo_distribution(available, player, view)
    assert len({weight for _, weight in distribution}) == 1
    assert distribution == model.combo_distribution(
        available, replace(player, position="UTG"), view
    )
    controller.process_action(state, PlayerAction.BET, 2)
    after = build_hand_state_view(state, controller)
    assert len({w for _, w in model.combo_distribution(available, player, after)}) > 1
    standard = replace(view, hand_variant="standard", forced_ante=None)
    assert len({w for _, w in model.combo_distribution(available, player, standard)}) > 1


def observation(ante=8, *, ruleset=MIXED_RULESET, quantum="1"):
    state = make_state(6)
    controller = HandController(Dealer(seed=7), bomb_pot_ante=ante)
    controller.start_hand(state)
    return from_public_state(
        build_hand_state_view(state, controller),
        get_legal_actions(state, controller),
        hand_id="sim:7",
        observation_id="1",
        big_blind=2,
        ruleset=ruleset,
        quantum=quantum,
    )


@pytest.mark.parametrize("ante", [None, 6, 8, 10])
def test_explicit_variant_round_trip_and_legacy_feature_refusal(ante):
    obs = observation(ante)
    obs.require_valid()
    assert obs.schema_version == VERSION_V2
    assert obs.hand_variant == (BOMB_VARIANT if ante else "standard")
    assert obs.forced_ante == (ante or 0)
    assert from_dict(obs.to_dict()) == obs
    for feature_set in ("raw-v1", "cards-v2"):
        with pytest.raises(SnapshotRejected, match="model_observation_version_mismatch"):
            encode(obs, feature_set=feature_set)
    encoded = encode(obs, feature_set="variants-v3")
    assert len(encoded.table) == 174
    assert encoded.table[-2] == float(ante is not None)
    assert encoded.table[-1] >= 0
    if ante is None:
        old = encode(observation(None, ruleset=RULESET), feature_set="cards-v2")
        assert encoded.table[:-2] == old.table
        assert encoded.players == old.players
    assert permute_encoded(encoded, [3, 1, 2, 0]).table[-2:] == encoded.table[-2:]


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("hand_variant", "double-board", "hand_variant_unsupported"),
        ("hand_variant", None, "hand_variant_unsupported"),
        ("forced_ante", None, "forced_ante_invalid"),
        ("forced_ante", True, "forced_ante_invalid"),
        ("forced_ante", 0, "forced_ante_invalid"),
        ("forced_ante", 9, "forced_ante_contributions_mismatch"),
        ("street", "preflop", "bomb_pot_preflop_unsupported"),
        ("source_blockers", ["unknown_source"], "unknown_source"),
        ("ruleset", RULESET, "ruleset_unverified_or_unsupported"),
    ],
)
def test_inconsistent_variant_state_and_source_refusals_are_preserved(field, value, reason):
    payload = observation().to_dict()
    payload[field] = value
    with pytest.raises(SnapshotRejected, match=reason):
        from_dict(payload)


def test_forced_money_uses_the_same_quantum_and_no_auto_upgrade_or_downgrade():
    obs = observation(quantum="0.01")
    assert obs.forced_ante == 800 and obs.big_blind == 200 and obs.pot == 4800
    assert (
        encode(obs, feature_set="variants-v3").table
        == encode(observation(), feature_set="variants-v3").table
    )
    old = observation(ruleset=RULESET)
    assert "hand_variant_unsupported" in old.blocking_reasons()
    with pytest.raises(SnapshotRejected, match="model_observation_version_mismatch"):
        encode(observation(None, ruleset=RULESET), feature_set="variants-v3")
    payload = obs.to_dict()
    payload["schema_version"] = "snapshot-observation/1"
    with pytest.raises(ValueError, match="fields"):
        from_dict(payload)
    standard = observation(None)
    standard.forced_ante = 8
    assert "standard_forced_ante_not_zero" in standard.blocking_reasons()
    bomb = observation()
    bomb.history = [{"street": "preflop", "action": "call"}]
    assert "bomb_pot_preflop_unsupported" in bomb.blocking_reasons()


def test_engine_variant_metadata_cannot_be_mislabeled_as_standard():
    state = make_state(6)
    controller = HandController(Dealer(seed=7), bomb_pot_ante=8)
    controller.start_hand(state)
    public = build_hand_state_view(state, controller)
    for corrupted in (
        replace(public, hand_variant="standard"),
        replace(public, hand_variant="unknown"),
        replace(public, forced_ante=None),
    ):
        result = from_public_state(
            corrupted,
            get_legal_actions(state, controller),
            hand_id="x",
            observation_id="1",
            big_blind=2,
            ruleset=MIXED_RULESET,
        )
        assert result.blocking_reasons()


def test_v3_checkpoint_round_trip_and_old_advisor_stops_before_forward(tmp_path, monkeypatch):
    model = SnapshotPolicy(seat_width=8, hidden_width=16, feature_set="variants-v3").eval()
    path = tmp_path / "unit_untrained.pt"
    data = checkpoint(model)
    assert data["schema_version"] == "snapshot-policy-checkpoint/3"
    torch.save(data, path)
    restored = load_checkpoint(path)
    batch = batch_tensors([encode(observation(), feature_set="variants-v3")])
    with torch.no_grad():
        a, b = model(**batch), restored(**batch)
        assert all(torch.equal(a[key], b[key]) for key in a)
    crossed = deepcopy(data)
    crossed["schema_version"] = "snapshot-policy-checkpoint/2"
    torch.save(crossed, path)
    with pytest.raises(ValueError, match="layout"):
        load_checkpoint(path)
    torch.save(checkpoint(SnapshotPolicy(feature_set="cards-v2")), path)
    advisor = SnapshotAdvisor(path, sizing_policy="expert-pot65-v1")

    def forbidden(*args, **kwargs):
        raise AssertionError("Legacy model must not receive variant observations")

    monkeypatch.setattr(advisor.model, "forward", forbidden)
    result = advisor.advise(observation().to_dict())
    assert result["blockers"] == ["model_observation_version_mismatch"]
    assert not result["model_called"]


def test_mixed_dataset_reproducibility_validation_and_separate_evaluation(tmp_path, monkeypatch):
    import poker.agents

    monkeypatch.setattr(poker.agents, "ExpertAgent", lambda **kwargs: Caller())
    kwargs = dict(hands=60, seed=611000, equity_samples=1, scenario="mixed-bomb-v1")
    directory = tmp_path / "data"
    first = dataset.prepare(directory, **kwargs)
    second = dataset.prepare(tmp_path / "repeat", **kwargs)
    assert first["split_sha256"] == second["split_sha256"]
    assert first["schema_version"] == "snapshot-dataset/2"
    assert first["layout_sha256"] == layout_hash("variants-v3")
    loaded, _ = dataset.load_dataset(directory, feature_set="variants-v3")
    variants = {r["observation"].hand_variant for rows in loaded.values() for r in rows}
    assert variants == {"standard", BOMB_VARIANT}
    for name in dataset.SPLITS:
        assert sum(first["variants"].get(f"{name}:{v}", 0) for v in variants) == len(loaded[name])
    with pytest.raises(ValueError, match="Incompatible dataset"):
        dataset.load_dataset(directory, feature_set="cards-v2")

    def forbidden(*args, **kwargs):
        raise AssertionError("This verification cannot train")

    monkeypatch.setattr(torch.optim, "AdamW", forbidden)
    report = training.preflight(directory, feature_set="variants-v3")
    assert report["table_feature_count"] == 174 and not report["policy_called"]
    model = SnapshotPolicy(seat_width=8, hidden_width=16, feature_set="variants-v3")
    path = tmp_path / "unit_untrained.pt"
    torch.save(checkpoint(model), path)
    evaluation = training.evaluate(directory, path, tmp_path / "eval")
    assert set(evaluation["variants"]) == variants
    assert sum(v["counts"]["samples"] for v in evaluation["variants"].values()) == len(
        loaded["test"]
    )
    assert not evaluation["training_run"]
    assert layout_for("variants-v3")["observation"] == VERSION_V2
    # Strict manifest selection: a V2 dataset cannot masquerade as the old format.
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    manifest["schema_version"] = dataset.DATASET_VERSION
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="Incompatible dataset"):
        dataset.load_dataset(directory, feature_set="variants-v3")
