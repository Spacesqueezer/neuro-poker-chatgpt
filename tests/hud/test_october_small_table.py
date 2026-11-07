import json
from pathlib import Path

import cv2
import pytest

from poker.hud.cards import find_cards
from poker.hud.recognition import configure_ocr, layout_panels
from poker.hud.session_images import saved_frame_path
from poker.hud.table_signals import controls, pot, read_bets

ROOT = Path("artifacts/hud/sessions/session_20261005_035204_be9e45")


def frame(n):
    path = saved_frame_path(ROOT, n)
    if not path.exists():
        pytest.skip("Local diagnostic source unavailable")
    configure_ocr()
    return cv2.imread(str(path))


@pytest.mark.parametrize("n", [76, 84, 86, 98, 101, 102])
def test_small_ten_with_chips_over_large_rank(n):
    board = [c for c in find_cards(frame(n)) if c.zone == "board"]
    assert [c.value for c in board][:3] == ["4c", "Tc", "Js"]
    assert board[1].confidence >= 75


@pytest.mark.parametrize("n", [895, 906, 911])
def test_small_pot_caption(n):
    events = [
        json.loads(line)
        for path in ROOT.glob("events.jsonl*")
        for line in path.read_text(encoding="utf8").splitlines()
    ]
    context = next(e["context"] for e in events if e["kind"] == "names" and e["frame_id"] == n)
    result = pot(frame(n), context["regions"])
    assert result["value"] == 5
    assert result["primary_evidence"]["value"] is None


def test_call_below_caption_at_native_scale():
    assert controls(frame(1496))["call_amount"] == 8


def test_hero_bet_while_slider_is_at_all_in():
    image = frame(906)
    assert read_bets(image, layout_panels(image))[6]["value"] == 2


def test_rejected_pot_cannot_be_replaced_by_loose_regional_words():
    from poker.hud.decision_stream import proposal
    from poker.hud.hand import HandObservation

    context = {
        "regions": {
            "table_text": {
                "words": [{"text": "Банк:", "confidence": 95}, {"text": "50", "confidence": 95}]
            }
        },
        "table_signals": {"pot": {"value": None}},
    }
    assert proposal(HandObservation(), [], context)["total_pot"] is None


def test_real_all_in_cap_combines_fast_pair_and_current_text_frame():
    from copy import deepcopy

    from poker.hud.bet_bridge import BetBridge

    image = frame(906)
    events = [
        json.loads(line)
        for path in ROOT.glob("events.jsonl*")
        for line in path.read_text(encoding="utf8").splitlines()
    ]
    fast = next(e for e in events if e["kind"] == "fast_table" and e["frame_id"] == 902)
    text = next(e for e in events if e["kind"] == "names" and e["frame_id"] == 906)
    facts = deepcopy(
        next(e for e in events if e["kind"] == "live_evidence" and e["frame_id"] == 906)
    )
    for key in (
        "stack_confirmations",
        "bet_confirmations",
        "participation_evidence",
        "empty_seat_confirmations",
    ):
        facts[key] = {int(k): v for k, v in facts[key].items()}
    oldfacts = deepcopy(fast["evidence"])
    for key in (
        "stack_confirmations",
        "bet_confirmations",
        "participation_evidence",
        "empty_seat_confirmations",
    ):
        oldfacts[key] = {int(k): v for k, v in oldfacts[key].items()}
    current = deepcopy(text["context"])
    reading = read_bets(image, layout_panels(image))[6]
    current["table_signals"]["slots"][6].update(current_bet=reading["value"], bet_evidence=reading)
    bridge = BetBridge()
    bridge.add({**fast, "image": str(saved_frame_path(ROOT, 902))}, fast["context"], oldfacts)
    combined = bridge.augment({**text, "image": str(saved_frame_path(ROOT, 906))}, current, facts)
    cap = combined["max_raise_confirmation"]
    assert cap["value"] == 129.59
    assert cap["hero_stack"]["value"] == 127.59
    assert cap["hero_current_bet"]["value"] == 2
    assert [s["frame_id"] for s in cap["confirmation_frames"]] == [897, 902, 906]
