"""User-facing confidence and probability labels shared with tests."""

import math
from datetime import datetime

from poker.hud.odds import CATEGORIES

GREEN = "#54db91"
YELLOW = "#ffce55"
RED = "#ff6b74"
SUIT_SYMBOLS = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}


def stack_text(roi, source, *, now=None):
    """Display the fresh checked reading, never the permissive name-reader text.

    source is LiveEvidence.previous and is discarded on capture/epoch boundaries.
    This is a single-frame display; decision requests still require confirmation.
    """
    unknown = "Стек не подтверждён"
    if not source:
        return unknown
    captured = datetime.fromisoformat(source["captured_at"])
    now = now or datetime.now(captured.tzinfo)
    if not 0 <= (now - captured).total_seconds() <= 5:
        return unknown
    context = source.get("context", {})
    nearby = [
        slot
        for slot in context.get("table_signals", {}).get("slots", [])
        if math.dist(roi[:2], slot["roi"][:2]) < slot["roi"][2] * 0.4
    ]
    if len(nearby) != 1:
        return unknown
    seat = nearby[0]["seat_index"]
    readings = context.get("stack_readings", {})
    reading = readings.get(seat, readings.get(str(seat), {}))
    value = reading.get("value")
    if (
        reading.get("rejection")
        or reading.get("error")
        or type(value) not in (float, int)
        or not math.isfinite(value)
        or value < 0
    ):
        return unknown
    return f"Стек: {value:.2f} р.".replace(".", ",", 1)


def name_color(seat):
    if seat.conflict:
        return RED
    if seat.manual:
        return GREEN
    score = seat.observation.confidence
    if not seat.observation.name or score < 65:
        return RED
    if seat.name and score >= 90:
        return GREEN
    return YELLOW


def card_text(cards):
    return (
        " ".join(
            ("10" if c[0] == "T" else c[0]) + SUIT_SYMBOLS[c[1]]
            if len(c) == 2 and c[1] in SUIT_SYMBOLS
            else "?"
            for c in cards
        )
        or "—"
    )


def hand_text(hand, confirmed):
    lines = [
        f"{hand.street} · {hand.phase}",
        f"Герой: {card_text(hand.hero)}",
        f"Борд: {card_text(hand.board)}",
    ]
    if not hand.valid:
        reasons = {
            "Low card confidence": "оценка одной из карт ниже 75%",
            "Unknown or duplicate card": "есть неизвестная или повторяющаяся карта",
            "Need two hero cards and 0/3/4/5 board cards": "неполный набор карт",
        }
        lines.append("Шансы недоступны: " + reasons.get(hand.issue, hand.issue or hand.phase))
        weak = [
            f"{card_text([c.value]) if c.value else '?'} — {c.confidence:.0f}%"
            for c in hand.cards
            if not c.value or c.confidence < 75
        ]
        if weak:
            lines.append("Проверить: " + "; ".join(weak))
    elif not confirmed:
        lines.append("Подтверждаем карты вторым кадром…")
    elif hand.odds:
        odds = hand.odds
        lines.append("Сейчас: " + CATEGORIES[odds["current_category"]])
        top = sorted(odds["probabilities"].items(), key=lambda item: item[1], reverse=True)[:3]
        approx = "≈" if odds["method"] == "monte_carlo" else ""
        improvement = odds.get(
            "improvement_probability",
            sum(
                p
                for rank, p in odds["probabilities"].items()
                if int(rank) > odds["current_category"]
            ),
        )
        lines.append(f"Усилить категорию к риверу: {approx}{improvement:.1%}")
        lines.append("Итог к риверу (не шанс победы):")
        lines.extend(
            f"{CATEGORIES[int(rank)]}: {approx}{probability:.1%}" for rank, probability in top
        )
        lines.append("Нажмите для всех комбинаций")
    return "\n".join(lines)
