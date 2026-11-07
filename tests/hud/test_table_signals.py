import json
from pathlib import Path

import cv2
import pytest

from poker.hud.decision_stream import proposal
from poker.hud.hand import HandObservation
from poker.hud.recognition import configure_ocr
from poker.hud.table_signals import TESSDATA, analyze_table, controls, locate_dealer

ROOT = Path(__file__).resolve().parents[2]
SESSION = ROOT / "artifacts/hud/sessions/session_20260910_092618_a572b1"


@pytest.mark.parametrize("number,action", [(871, "call"), (2009, "bet")])
def test_action_glow_does_not_move_seat_regions(number, action):
    path = ROOT / f"artifacts/hud/sessions/session_20260910_202646_6464df/frames/{number:08}.jpg"
    if not path.exists() or not (TESSDATA / "rus.traineddata").exists():
        pytest.skip("Local diagnostic frames / optional Russian OCR data unavailable")
    configure_ocr()
    signals = analyze_table(cv2.imread(str(path)), {}, [])
    assert len(signals["slots"]) == 7
    assert signals["slots"][4]["action_label"]["action"] == action


def frame(number):
    path = SESSION / f"frames/{number:08d}.jpg"
    if not path.exists() or not (TESSDATA / "rus.traineddata").exists():
        pytest.skip("Local diagnostic frames / optional Russian OCR data unavailable")
    configure_ocr()
    return cv2.imread(str(path))


def test_check_button_pot_and_dealer_on_recorded_flop():
    image = frame(246)
    rows = [
        json.loads(line)
        for line in (SESSION / "events.jsonl").read_text(encoding="utf8").splitlines()
    ]
    context = next(
        row["context"] for row in rows if row["kind"] == "names" and row["frame_id"] == 246
    )
    signals = analyze_table(image, context["regions"], context["dealer_candidates"])
    assert signals["pot"]["value"] == 4.73
    assert signals["controls"]["call_amount"] == 0
    assert signals["controls"]["flags"] == dict(
        can_fold=True, can_check=True, can_call=False, can_bet=True, can_raise=False
    )
    assert signals["dealer_slot"] == 0
    assert signals["slots"][3]["action_label"]["action"] == "check"


def test_preflop_call_raise_and_visible_player_bets():
    signals = analyze_table(frame(328), {}, [])
    assert signals["controls"]["call_amount"] == 2
    assert signals["controls"]["flags"]["can_raise"] is True
    assert signals["controls"]["flags"]["can_check"] is False
    assert [signals["slots"][i]["current_bet"] for i in (1, 3, 6)] == [4, 1, 2]
    assert signals["slots"][0]["current_bet"] is None
    assert signals["slots"][3]["action_label"]["action"] == "fold"
    request = proposal(
        HandObservation(hero=("Ah", "Th"), my_turn=True), [], {"table_signals": signals}
    )
    assert [p["seat_index"] for p in request["players"]] == list(range(7))
    assert request["players"][3]["is_active"] is False
    assert request["max_raise_amount"] is None  # Selected slider value is not a legal bound.
    assert request["can_all_in"] is None


def test_grey_pre_action_buttons_never_become_legal_actions():
    assert controls(frame(1378))["flags"] == {}


@pytest.mark.parametrize(
    "number,action,value",
    [(1908, "all_in", 341.88), (1910, "all_in", 341.88), (1912, "raise", 65.0)],
)
def test_slider_all_in_and_interior_amount_on_saved_frames(number, action, value):
    path = ROOT / f"artifacts/hud/sessions/session_20260912_074919_b1e521/frames/{number:08d}.jpg"
    if not path.exists() or not (TESSDATA / "rus.traineddata").exists():
        pytest.skip("Local diagnostic frames / optional Russian OCR data unavailable")
    configure_ocr()
    result = controls(cv2.imread(str(path)))
    assert result["selected_wager"]["action"] == action
    assert result["selected_wager"]["value"] == value
    assert result["flags"].get("can_all_in") is (True if action == "all_in" else None)
    assert result["min_raise_amount"] is None
    assert result["max_raise_amount"] is None
    request = proposal(
        HandObservation(hero=("Ts", "8h"), my_turn=True),
        [],
        {"table_signals": {"controls": result}},
    )
    assert request["can_all_in"] is (True if action == "all_in" else None)


def test_ambiguous_dealer_is_not_assigned():
    rois = [(0, 0, 100, 40), (200, 0, 100, 40)]
    assert locate_dealer(rois, [{"roi": [140, 10, 20, 20]}]) is None
    assert locate_dealer(rois, []) is None


@pytest.mark.parametrize(
    "number,seat,expected",
    [
        (381, 4, "big_blind"),
        (381, 6, "small_blind"),
        (836, 5, "small_blind"),
        (836, 6, "big_blind"),
        (381, 0, None),
    ],
)
def test_blinds_on_saved_frames_are_separate_from_actions(number, seat, expected):
    from poker.hud.recognition import layout_panels
    from poker.hud.table_signals import read_action_label, read_blind_label

    path = ROOT / f"artifacts/hud/sessions/session_20260911_012959_8898f1/frames/{number:08d}.jpg"
    if not path.exists() or not (TESSDATA / "rus.traineddata").exists():
        pytest.skip("Local diagnostic images / Russian OCR unavailable")
    configure_ocr()
    image = cv2.imread(str(path))
    roi = layout_panels(image)[seat]
    assert (read_blind_label(image, roi) or {}).get("blind") == expected
    assert read_action_label(image, roi) is None


@pytest.mark.parametrize("number,expected", [(403, 16), (84, 2), (1077, 3), (1813, None)])
def test_call_amount_on_recorded_live_button(number, expected):
    path = ROOT / f"artifacts/hud/sessions/session_20260911_020140_b8974b/frames/{number:08d}.jpg"
    if not path.exists() or not (TESSDATA / "rus.traineddata").exists():
        pytest.skip("Local images / Russian OCR unavailable")
    configure_ocr()
    result = controls(cv2.imread(str(path)))
    assert result["call_amount"] == expected
    assert result["flags"]["can_call"] is True
    assert result["min_raise_amount"] is None
    assert result["max_raise_amount"] is None
    if number == 84:
        assert result["selected_wager"]["value"] == 4
        assert result["selected_wager"]["semantics"] == "selected_button_amount_not_legal_bound"


@pytest.mark.parametrize(
    "secondary,score,accepted", [("16", 96, True), ("17", 99, False), ("16", 84, False)]
)
def test_button_number_requires_independent_agreement(
    monkeypatch, request, secondary, score, accepted
):
    import numpy as np

    from poker.hud import table_signals

    table_signals.numeric_words.cache_clear()
    request.addfinalizer(table_signals.numeric_words.cache_clear)
    results = iter([{"text": ["1"], "conf": [35]}, {"text": [secondary], "conf": [score]}])
    monkeypatch.setattr(table_signals.pytesseract, "image_to_data", lambda *a, **kw: next(results))
    result = table_signals.button_number(
        np.zeros((60, 60, 3), np.uint8),
        (0, 0, 50, 50),
        {"text": "16", "confidence": 95, "roi": [10, 10, 18, 19]},
    )
    assert (result["value"] == 16 and result["confidence"] >= 85) is accepted
