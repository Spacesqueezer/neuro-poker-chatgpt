from pathlib import Path

import cv2
import numpy as np
import pytest

from poker.hud import table_signals
from poker.hud.recognition import configure_ocr

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("frame,call,selected", [(626, 16, 38), (1188, 5, 8)])
def test_currency_row_below_clipped_button_caption(frame, call, selected):
    path = ROOT / f"artifacts/hud/sessions/session_20260930_112040_26d4d3/ocr_frames/{frame:08}.png"
    if not path.exists():
        pytest.skip("Local diagnostic image unavailable")
    configure_ocr()
    reading = table_signals.controls(cv2.imread(str(path)))
    assert reading["call_amount"] == call
    assert reading["selected_wager"]["value"] == selected
    assert reading["min_raise_amount"] is None
    assert reading["max_raise_amount"] is None


@pytest.mark.parametrize(
    "rows,expected",
    [
        ([0, 1, *range(6, 30)], 4),
        (list(range(6, 30)), None),
        (list(range(30)), None),
        ([*range(6), *range(10, 30)], None),
        ([0, 1, 6, 7, 14, 15], None),
    ],
)
def test_currency_row_separation_preserves_complete_glyphs(rows, expected):
    mask = np.zeros((39, 133), np.uint8)
    mask[rows, 40:60] = 255
    assert table_signals.currency_row_start(mask) == expected


@pytest.mark.parametrize("frame", [278, 709, 713, 716, 720, 724, 728])
def test_small_jpeg_call_currency_recovery(frame):
    path = ROOT / f"artifacts/hud/sessions/session_20260923_054209_82f838/frames/{frame:08}.jpg"
    if not path.exists():
        pytest.skip("Local diagnostic frame unavailable")
    configure_ocr()
    reading = table_signals.controls(cv2.imread(str(path)))
    assert reading["call_amount"] == 1
    assert reading["flags"]["can_call"] is True
    assert reading["min_raise_amount"] is None


def test_call_retry_cannot_override_previous_line_conflict(monkeypatch):
    path = ROOT / "artifacts/hud/sessions/session_20260923_054209_82f838/frames/00000278.jpg"
    if not path.exists():
        pytest.skip("Local diagnostic frame unavailable")
    configure_ocr()
    monkeypatch.setattr(
        table_signals,
        "currency_line",
        lambda *a: {"value": None, "readings": [{"value": 3}, {"value": None}]},
    )
    monkeypatch.setattr(table_signals, "selected_currency_amount", lambda *a: {"value": 1})
    reading = table_signals.controls(cv2.imread(str(path)))
    assert reading["call_amount"] is None
    evidence = [
        b["currency_recovery_evidence"]
        for b in reading["buttons"]
        if "currency_recovery_evidence" in b
    ]
    assert evidence[0]["prior_line_conflicts"] == [3]


@pytest.mark.parametrize(
    "score,number,expected", [(85, 56.7, None), (84, 56.7, 5.67), (95, 5.67, 5.67)]
)
@pytest.mark.parametrize("source", ["word", "numeric"])
def test_full_line_does_not_override_confident_numeric_conflict(score, number, expected, source):
    button = {"words": [], "full_line_evidence": {"value": 5.67}}
    if source == "word":
        button["words"] = [{"text": str(number), "confidence": score}]
    else:
        button["number_evidence"] = {"value": number, "confidence": score}
    assert table_signals.corroborated_line_value(button) == expected


@pytest.mark.parametrize(
    "second,score,expected",
    [
        ("5,67 p.", 85, 5.67),
        ("5,67 p.", 84, None),
        ("56,7 p.", 95, None),
        ("5,67", 95, None),
        ("S,67 p.", 95, None),
    ],
)
def test_full_currency_line_rejects_conflicts_and_missing_currency(
    monkeypatch, second, score, expected
):
    table_signals.currency_line.cache_clear()
    readings = iter([("5.67 p.", 92), (second, score)])

    def ocr(*args, **kwargs):
        text, confidence = next(readings)
        return {"text": text.split(), "conf": [confidence] * len(text.split())}

    monkeypatch.setattr(table_signals.pytesseract, "image_to_data", ocr)
    image = np.zeros((30, 100, 3), np.uint8)
    assert table_signals.currency_line(image.shape, image.tobytes())["value"] == expected
    table_signals.currency_line.cache_clear()


@pytest.mark.parametrize("number", [397, 402])
def test_decimal_call_keeps_currency_and_separator(number):
    path = ROOT / f"artifacts/hud/sessions/session_20260914_083437_99b85d/frames/{number:08d}.jpg"
    if not path.exists() or not (table_signals.TESSDATA / "rus.traineddata").exists():
        pytest.skip("Local diagnostic frame / Russian OCR unavailable")
    configure_ocr()
    result = table_signals.controls(cv2.imread(str(path)))
    assert result["call_amount"] == 5.67
    assert result["buttons"][1]["full_line_evidence"]["value"] == 5.67


def test_currency_misread_as_digit_is_reread_from_pixels():
    path = ROOT / "artifacts/hud/sessions/session_20260914_083437_99b85d/frames/00000334.jpg"
    if not path.exists() or not (table_signals.TESSDATA / "rus.traineddata").exists():
        pytest.skip("Local diagnostic frame / Russian OCR unavailable")
    configure_ocr()
    result = table_signals.controls(cv2.imread(str(path)))
    assert result["call_amount"] == 3
    button = result["buttons"][1]
    assert any(w["text"] == "32." for w in button["words"])
    assert button["currency_number_evidence"]["value"] == 3
    assert result["min_raise_amount"] is None
    assert result["max_raise_amount"] is None


@pytest.mark.parametrize(
    "text,score,values,expected",
    [
        ("2р.", 84, [2], 2),
        ("2р.", 79, [2], None),
        ("Зр.", 99, [3], None),
        ("2р.", 90, [2, 3], None),
        ("2р.", 90, [], None),
        ("2", 99, [2], None),
    ],
)
def test_fused_currency_needs_numeric_primary_and_no_conflicting_read(
    text, score, values, expected
):
    readings = [{"value": v, "confidence": 90} for v in values]
    assert (
        table_signals.confirm_fused_currency({"text": text, "confidence": score}, readings)
        == expected
    )


@pytest.mark.parametrize("number", [258, 265])
def test_small_window_fused_two_ruble_call(number):
    path = ROOT / f"artifacts/hud/sessions/session_20260913_161745_1e250e/frames/{number:08d}.jpg"
    if not path.exists() or not (table_signals.TESSDATA / "rus.traineddata").exists():
        pytest.skip("Local diagnostic frame / Russian OCR unavailable")
    configure_ocr()
    assert table_signals.controls(cv2.imread(str(path)))["call_amount"] == 2


@pytest.mark.parametrize(
    "second,score,expected",
    [("5 p.", 85, 5), ("2 p.", 99, None), ("5 p.", 84, None), ("Sp.", 99, None), ("5", 99, None)],
)
def test_small_currency_requires_two_strict_readings(monkeypatch, second, score, expected):
    table_signals.small_currency_amount.cache_clear()
    readings = iter([("5 p.", 86), (second, score)])

    def ocr(*args, **kwargs):
        text, confidence = next(readings)
        return {"text": text.split(), "conf": [confidence] * len(text.split())}

    monkeypatch.setattr(table_signals.pytesseract, "image_to_data", ocr)
    image = np.zeros((10, 20, 3), np.uint8)
    assert table_signals.small_currency_amount(image.shape, image.tobytes())["value"] == expected
    table_signals.small_currency_amount.cache_clear()


@pytest.mark.parametrize("number", [1951, 1952, 1954])
def test_small_five_on_recorded_call_button(number):
    path = ROOT / f"artifacts/hud/sessions/session_20260912_074919_b1e521/frames/{number:08d}.jpg"
    if not path.exists() or not (table_signals.TESSDATA / "rus.traineddata").exists():
        pytest.skip("Local diagnostic frame / Russian OCR unavailable")
    configure_ocr()
    result = table_signals.controls(cv2.imread(str(path)))
    assert result["call_amount"] == 5
    assert result["min_raise_amount"] is None
    assert result["max_raise_amount"] is None


@pytest.mark.parametrize("number", [1555, 1556])
def test_one_ruble_recovers_without_letter_substitution(number):
    path = ROOT / f"artifacts/hud/sessions/session_20260911_020140_b8974b/frames/{number:08d}.jpg"
    if not path.exists():
        pytest.skip("Local diagnostic frame unavailable")
    configure_ocr()
    bet = {"value": None, "text": "Тр.", "roi": [956, 415, 100, 32]}
    result = table_signals.recover_amount(cv2.imread(str(path)), bet)
    assert result["value"] == 1
    assert result["grayscale_evidence"]["confidence"] >= 85
    assert bet["value"] is None
    assert result["text"] == "Тр."


def test_known_amount_and_no_currency_skip_retry(monkeypatch):
    def unexpected(*args):
        pytest.fail("Unnecessary OCR")

    monkeypatch.setattr(table_signals, "grayscale_amount", unexpected)
    frame = np.zeros((30, 30, 3), np.uint8)
    for bet in ({"value": 12, "text": "12р."}, {"value": None, "text": "1"}):
        assert table_signals.recover_amount(frame, bet) is bet


@pytest.mark.parametrize(
    "text,score,expected",
    [
        ("1 p.", 85, 1),
        ("19.54 p.", 90, 19.54),
        ("1 p.", 84, None),
        ("Tp.", 99, None),
        ("1", 99, None),
        ("1 p. 2", 99, None),
        ("1,234 p.", 99, None),
    ],
)
def test_grayscale_parser_rejects_letters_low_confidence_and_extra_text(
    monkeypatch, text, score, expected
):
    table_signals.grayscale_amount.cache_clear()
    monkeypatch.setattr(
        table_signals.pytesseract,
        "image_to_data",
        lambda *args, **kwargs: {"text": text.split(), "conf": [score] * len(text.split())},
    )
    image = np.zeros((10, 20, 3), np.uint8)
    assert table_signals.grayscale_amount(image.shape, image.tobytes())["value"] == expected
    table_signals.grayscale_amount.cache_clear()


def test_cli_passes_amount_recovery_flag(tmp_path, monkeypatch):
    import sys

    from tools import replay_hud_hands

    session = tmp_path / "session"
    session.mkdir()
    cache = tmp_path / "observations.jsonl"
    cache.write_text("")
    received = []
    monkeypatch.setattr(replay_hud_hands, "configure_ocr", lambda: None)
    monkeypatch.setattr(replay_hud_hands, "replay", lambda *args: received.append(args) or {})
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "replay_hud_hands.py",
            str(session),
            "--refresh-labels",
            str(cache),
            "--recover-amounts",
            "--output",
            str(tmp_path / "result"),
        ],
    )
    replay_hud_hands.main()
    assert received[0][5] is True


@pytest.mark.parametrize("number,expected", [(47, 1), (378, 4.26)])
def test_held_out_session_amounts(number, expected):
    from poker.hud.recognition import layout_panels

    path = ROOT / f"artifacts/hud/sessions/session_20260910_202646_6464df/frames/{number:08d}.jpg"
    if not path.exists() or not (table_signals.TESSDATA / "rus.traineddata").exists():
        pytest.skip("Local diagnostic images / Russian OCR unavailable")
    configure_ocr()
    frame = cv2.imread(str(path))
    bets = table_signals.read_bets(frame, layout_panels(frame))
    assert bets[1]["value"] == expected


def test_winning_amount_is_not_a_new_bet():
    path = ROOT / "artifacts/hud/sessions/session_20260911_020140_b8974b/frames/00002379.jpg"
    if not path.exists() or not (table_signals.TESSDATA / "rus.traineddata").exists():
        pytest.skip("Local diagnostic images / Russian OCR unavailable")
    configure_ocr()
    result = table_signals.analyze_table(cv2.imread(str(path)), {}, [])
    winner = result["slots"][1]
    assert winner["settlement_label"]["phase"] == "pot_awarded"
    assert winner["current_bet"] is None
    assert winner["payout_evidence"]["value"] == 39.69


@pytest.mark.parametrize("frame", [694, 701, 705, 732, 1664, 1672, 1676])
def test_september23_one_ruble_call(frame):
    path = ROOT / f"artifacts/hud/sessions/session_20260923_054209_82f838/requests/{frame:08d}.png"
    if not path.exists():
        pytest.skip("Local diagnostic image unavailable")
    configure_ocr()
    result = table_signals.controls(cv2.imread(str(path)))
    assert result["call_amount"] == 1
    assert result["min_raise_amount"] is None
    assert result["max_raise_amount"] is None


@pytest.mark.parametrize(
    "second,score,expected",
    [
        ("1p.", 85, 1),
        ("1p.", 84, None),
        ("7p.", 95, None),
        ("1", 95, None),
        ("Tp.", 95, None),
        ("1.00p.", 90, 1),
    ],
)
def test_polarity_currency_requires_agreement(monkeypatch, second, score, expected):
    table_signals.polarity_currency_amount.cache_clear()
    readings = iter([("1p.", 90), (second, score)])

    def ocr(*args, **kwargs):
        text, confidence = next(readings)
        return {"text": [text], "conf": [confidence]}

    monkeypatch.setattr(table_signals.pytesseract, "image_to_data", ocr)
    image = np.zeros((28, 38, 3), np.uint8)
    assert table_signals.polarity_currency_amount(image.shape, image.tobytes())["value"] == expected
    table_signals.polarity_currency_amount.cache_clear()


@pytest.mark.parametrize("text", ["56.7p.", "56,7 р.", "56.7"])
def test_currency_line_rejects_confident_currency_conflict(text):
    button = {"words": [{"text": text, "confidence": 95}], "full_line_evidence": {"value": 5.67}}
    assert table_signals.corroborated_line_value(button) is None


@pytest.mark.parametrize("frame,expected", [(694, 4), (701, 4), (705, 4), (732, 4), (1664, 4)])
def test_selected_currency_is_not_a_raise_bound(frame, expected):
    path = ROOT / f"artifacts/hud/sessions/session_20260923_054209_82f838/requests/{frame:08d}.png"
    if not path.exists():
        pytest.skip("Local diagnostic image unavailable")
    configure_ocr()
    result = table_signals.controls(cv2.imread(str(path)))
    assert result["selected_wager"]["value"] == expected
    assert result["min_raise_amount"] is None
    assert result["max_raise_amount"] is None


@pytest.mark.parametrize(
    "frame,expected",
    [
        (445, 6),
        (450, 6),
        (743, 2),
        (851, 2),
        (858, 2),
        (885, 2),
        (976, 2),
        (980, 2),
        (1037, 2),
        (1059, 2),
        (1153, 2),
        (1158, 2),
        (1189, 2),
        (1257, 2),
        (1676, 7),
    ],
)
def test_recovered_selected_amount(frame, expected):
    path = ROOT / f"artifacts/hud/sessions/session_20260923_054209_82f838/requests/{frame:08d}.png"
    if not path.exists():
        pytest.skip("Local diagnostic image unavailable")
    configure_ocr()
    result = table_signals.controls(cv2.imread(str(path)))
    assert result["selected_wager"]["value"] == expected
    assert result["min_raise_amount"] is None
    assert result["max_raise_amount"] is None


def test_selected_recovery_preserves_strong_conflict(monkeypatch):
    table_signals.selected_currency_amount.cache_clear()
    values = iter(
        [
            {"value": None, "readings": [{"value": 20}, {"value": None}]},
            {"value": 2, "readings": [{"value": 2}, {"value": 2}]},
        ]
    )
    monkeypatch.setattr(table_signals, "polarity_currency_amount", lambda *args: next(values))
    crop = np.full((30, 100, 3), 255, np.uint8)
    result = table_signals.selected_currency_amount(crop.shape, crop.tobytes())
    assert result["value"] is None
    assert result["conflicting_values"] == [20]
    table_signals.selected_currency_amount.cache_clear()


@pytest.mark.parametrize("score,expected", [(84, 13.64), (85, None), (93, None)])
def test_bet_fallback_cannot_override_confident_digit_conflict(score, expected):
    original = {
        "value": 13.64,
        "words": [],
        "number_evidence": {"value": 15.64, "confidence": score},
    }
    result = table_signals.corroborated_bet(original)
    assert result["value"] == expected
    assert original["value"] == 13.64


def test_alternate_bet_position_uses_its_own_numeric_evidence():
    result = table_signals.corroborated_bet(
        {
            "value": 2,
            "words": [],
            "number_evidence": {"value": 1, "confidence": 95},
            "position_evidence": {"value": 2, "words": []},
        }
    )
    assert result["value"] == 2


@pytest.mark.parametrize("frame", [908, 910])
def test_recorded_turn_bet_conflict_is_unknown_not_wrong_confirmed_amount(frame):
    path = ROOT / f"artifacts/hud/sessions/session_20261005_122501_a8209d/ocr_frames/{frame:08}.png"
    if not path.exists():
        pytest.skip("Local diagnostic image unavailable")
    configure_ocr()
    bet = table_signals.read_bets(cv2.imread(str(path)), [[323, 216, 170, 67]])[0]
    assert bet["value"] is None
    assert bet["consistency_evidence"]["value"] == 13.64
    assert bet["consistency_evidence"]["conflicting_values"] == [15.64]
