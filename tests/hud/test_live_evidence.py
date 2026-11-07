from datetime import datetime, timedelta

from poker.hud.live_evidence import LiveEvidence
from tests.hud.test_confirmed_bets import row


def feed(live, number, *, epoch=None, **changes):
    item = row(number)
    item.update(changes)
    item["evidence_epoch"] = live.epoch if epoch is None else epoch
    item["context"]["table_signals"]["slots"][0]["card_back_evidence"] = {"present": True}
    return live.update(
        item["context"],
        {k: v for k, v in item.items() if k != "context"},
        now=datetime.fromisoformat(item["captured_at"]),
    )


def test_live_confirms_same_source_bets_and_participation_without_ocr():
    live = LiveEvidence()
    assert not feed(live, 1)["bet_confirmations"]
    assert not feed(live, 2)["bet_confirmations"]
    facts = feed(live, 3)
    assert facts["bet_confirmations"][0]["value"] == 2
    assert facts["participation_evidence"][0]["cards_dealt"] is True
    payload = {
        "players": [{"seat_index": 0, "name": "manual_name"}, {"seat_index": 1, "current_bet": 999}]
    }
    live.apply(payload, facts)
    assert payload["players"][0]["name"] == "manual_name"
    assert payload["players"][0]["current_bet"] == 2
    assert payload["players"][1]["current_bet"] is None
    assert payload["players"][1]["cards_dealt"] is None
    assert facts["model_called"] is False


def test_live_stacks_require_repeated_fresh_reading_and_reset_on_missing_or_pause():
    live = LiveEvidence()

    def sample(n, readings):
        item = row(n)
        item["context"]["stack_readings"] = readings
        return feed(live, n, context=item["context"])

    reading = {"value": 100, "confidence": 90, "roi": [1, 2, 30, 10]}
    assert not sample(1, {"0": reading})["stack_confirmations"]
    facts = sample(2, {"0": reading})
    assert facts["stack_confirmations"][0]["value"] == 100
    payload = {"players": [{"seat_index": 0, "stack": 999}, {"seat_index": 1, "stack": 999}]}
    live.apply(payload, facts)
    assert [p["stack"] for p in payload["players"]] == [100, None]
    assert not sample(3, {})["stack_confirmations"]
    assert not sample(4, {0: reading})["stack_confirmations"]
    live.reset()
    assert not sample(5, {0: reading})["stack_confirmations"]
    moved = {**reading, "roi": [5, 2, 30, 10]}
    assert not sample(6, {0: moved})["stack_confirmations"]


def test_live_excludes_only_repeated_empty_icon_without_hand_evidence():
    from copy import deepcopy

    live = LiveEvidence()
    facts = None
    for n in (1, 2):
        item = row(n)
        item["context"]["empty_seat_readings"] = {1: {"empty": True, "roi": [1, 2, 30, 40]}}
        facts = feed(live, n, context=item["context"])
    assert facts["empty_seat_confirmations"][1]["occupied"] is False
    payload = {"players": [{"seat_index": 1, "stack": None, "current_bet": None}]}
    before = deepcopy(facts)
    assert live.apply(deepcopy(payload), facts)["players"] == []
    assert facts == before  # Recorder may already own this evidence object.
    payload["players"][0]["current_bet"] = 2
    assert len(live.apply(deepcopy(payload), facts)["players"]) == 1
    facts["hand_participants"] = ["1"]
    payload["players"][0]["current_bet"] = None
    assert len(live.apply(payload, facts)["players"]) == 1
    live.reset()
    assert not feed(live, 3, context=item["context"])["empty_seat_confirmations"]


def test_pause_epoch_discards_late_worker_and_requires_new_confirmation():
    live = LiveEvidence()
    for n in (1, 2, 3):
        feed(live, n)
    old_epoch = live.epoch
    live.reset()
    assert feed(live, 4, epoch=old_epoch) is None
    assert live.previous is None
    assert not feed(live, 5)["bet_confirmations"]
    assert not feed(live, 6)["bet_confirmations"]
    assert feed(live, 7)["bet_confirmations"]


def test_stale_result_resets_confirmation_and_duplicate_cannot_confirm():
    live = LiveEvidence()
    feed(live, 1)
    assert feed(live, 1) is None
    item = row(2)
    item["evidence_epoch"] = live.epoch
    assert (
        live.update(
            item["context"],
            item,
            now=datetime.fromisoformat(item["captured_at"]) + timedelta(seconds=6),
        )
        is None
    )
    assert live.previous is None


def test_window_change_does_not_carry_old_hand_facts():
    live = LiveEvidence()
    for n in (1, 2, 3):
        feed(live, n)
    facts = feed(live, 4, window="other")
    assert not facts["bet_confirmations"] and not facts["participation_evidence"]
    assert not live.tracker.hands


def test_queued_evidence_cannot_acquire_facts_from_a_future_frame():
    live = LiveEvidence()
    for n in (1, 2, 3):
        facts = feed(live, n)
    before = list(facts["participation_evidence"][0]["evidence"])
    live.tracker.current["participants"]["0"]["evidence"].append({"kind": "future_frame"})
    assert facts["participation_evidence"][0]["evidence"] == before
