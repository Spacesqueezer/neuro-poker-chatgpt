import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from poker.hud.hand import observe
from poker.hud.models import CardObservation
from poker.hud.presentation import hand_text, stack_text


def test_visible_low_confidence_card_explains_why_odds_are_blocked():
    cards = [
        CardObservation("hero", (0, 0, 100, 140), value, score)
        for value, score in [("9d", 68), ("As", 95)]
    ]
    hand = observe(cards)
    text = hand_text(hand, False)
    assert "ниже 75%" in text and "9♦ — 68%" in text
    assert "Усилить категорию" not in text and hand.odds is None


def source(value):
    return {
        "captured_at": "2026-10-19T04:00:00+00:00",
        "context": {
            "table_signals": {"slots": [{"seat_index": 3, "roi": [1074, 395, 172, 67]}]},
            "stack_readings": {"3": {"value": value}},
        },
    }


def test_stack_display_uses_checked_amount_and_expires():
    at = datetime(2026, 10, 19, 4, tzinfo=UTC)
    roi = [1076, 394, 171, 67]
    assert stack_text(roi, source(55.48), now=at) == "Стек: 55,48 р."
    assert stack_text(roi, source(0), now=at) == "Стек: 0,00 р."
    assert stack_text(roi, source(None), now=at) == "Стек не подтверждён"
    assert stack_text(roi, source(55.48), now=at + timedelta(seconds=6)) == "Стек не подтверждён"
    assert stack_text(roi, source(55.48), now=at - timedelta(seconds=1)) == "Стек не подтверждён"
    assert stack_text(roi, None, now=at) == "Стек не подтверждён"
    assert stack_text([100, 395, 172, 67], source(55.48), now=at) == "Стек не подтверждён"
    ambiguous = deepcopy(source(55.48))
    ambiguous["context"]["table_signals"]["slots"] *= 2
    assert stack_text(roi, ambiguous, now=at) == "Стек не подтверждён"


@pytest.mark.parametrize("value", [True, -1, float("nan"), float("inf"), "55.48"])
def test_invalid_display_amounts_remain_unknown(value):
    assert (
        stack_text([1076, 394, 171, 67], source(value), now=datetime(2026, 10, 19, 4, tzinfo=UTC))
        == "Стек не подтверждён"
    )


def test_recorded_almina_phantom_digits_are_not_shown():
    session = Path("artifacts/hud/sessions/session_20261019_071128_4d77cb")
    if not (session / "events.jsonl").exists():
        pytest.skip("Local diagnostic source unavailable")
    rows = [
        r
        for path in session.glob("events.jsonl*")
        for line in path.read_text(encoding="utf-8").splitlines()
        if (r := json.loads(line))["kind"] == "names" and r["frame_id"] in (563, 614)
    ]
    assert len(rows) == 2
    for row in rows:
        player = next(p for p in row["players"] if p["name"] == "almina")
        label = stack_text(player["roi"], row, now=datetime.fromisoformat(row["at"]))
        if row["frame_id"] == 563:
            assert player["stack"] == "99,48 p."
            assert label == "Стек: 55,48 р."
        else:
            assert player["stack"] == "7 52,48 p."
            assert label == "Стек не подтверждён"
