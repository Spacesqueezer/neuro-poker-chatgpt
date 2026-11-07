"""Window-title stakes with capture/hand binding; never attest a hand's rules."""

import math
import re
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from typing import Any, cast

_AMOUNT = r"[0-9]+(?:[.,][0-9]{1,2})?"
_TITLE = re.compile(
    rf"(?P<name>[^\r\n]+?)\s+#(?P<table>[0-9]+)\s+-\s+"
    rf"(?P<sb>{_AMOUNT})\s*р\./\s*(?P<bb>{_AMOUNT})\s*р\.,\s*"
    r"(?P<features>[^\r\n]*?)БЛ\s+Холдем\s+-\s+Рука:\s*(?P<hand>[0-9]+)",
    re.IGNORECASE,
)
_BINDING = (
    "frame_id",
    "captured_at",
    "window",
    "window_handle",
    "client_rect",
    "evidence_epoch",
    "hero_seat",
    "window_title_capture",
)


def parse_title_stakes(title: Any) -> dict[str, Any] | None:
    """Recognize only the recorded PokerDom RUB NLHE title grammar."""
    if not isinstance(title, str) or len(title) > 1024:
        return None
    match = _TITLE.fullmatch(title.strip())
    if not match:
        return None
    sb, bb = (Decimal(match[k].replace(",", ".")) for k in ("sb", "bb"))
    if not 0 < sb <= bb <= Decimal("10000000000"):
        return None
    return {
        "table_name": match["name"],
        "table_id": match["table"],
        "title_hand_id": match["hand"],
        "small_blind": format(sb, "f"),
        "big_blind": format(bb, "f"),
        "currency": "RUB",
        "advertised_features": match["features"].strip(),
        "bomb_pot_schedule_advertised": "взрывной банк" in match["features"].casefold(),
        "ruleset_verified": False,
        "current_hand_is_bomb_pot": None,
    }


def _sample(source: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any] | None:
    capture = source.get("window_title_capture")
    if not isinstance(capture, dict) or capture.get("before") != capture.get("after"):
        return None
    parsed = parse_title_stakes(capture.get("after"))
    confidence = cast(float, identity.get("confidence"))
    if (
        parsed is None
        or type(confidence) not in (int, float)
        or not math.isfinite(confidence)
        or confidence < 80
        or str(identity.get("value")) != parsed["title_hand_id"]
        or type(source.get("window_handle")) is not int
        or source["window_handle"] <= 0
        or type(source.get("evidence_epoch")) is not int
        or type(source.get("frame_id")) is not int
        or not isinstance(source.get("client_rect"), (list, tuple))
        or len(source["client_rect"]) != 4
    ):
        return None
    try:
        datetime.fromisoformat(source["captured_at"])
    except (KeyError, ValueError, TypeError):
        return None
    binding: dict[str, Any] = {key: deepcopy(source.get(key)) for key in _BINDING}
    binding["client_rect"] = list(binding["client_rect"])
    return {"source": binding, "screen_identity": deepcopy(identity), "parsed": parsed}


def _pair(first: dict[str, Any], second: dict[str, Any]) -> bool:
    a, b = first["source"], second["source"]
    try:
        elapsed = (
            datetime.fromisoformat(b["captured_at"]) - datetime.fromisoformat(a["captured_at"])
        ).total_seconds()
    except (TypeError, ValueError):
        return False
    return (
        0 < elapsed <= 5
        and a["frame_id"] != b["frame_id"]
        and all(a[key] == b[key] for key in _BINDING if key not in ("frame_id", "captured_at"))
        and first["parsed"] == second["parsed"]
    )


def confirmed_title_stakes(
    evidence: dict[str, Any], source: dict[str, Any], identity: dict[str, Any]
) -> dict[str, Any] | None:
    """Revalidate the exact two source captures before filling monetary fields."""
    frames = evidence.get("confirmation_frames", [])
    if evidence.get("status") != "confirmed" or len(frames) != 2:
        return None
    current = _sample(source, identity)
    try:
        first = _sample(frames[0]["source"], frames[0]["screen_identity"])
    except (KeyError, TypeError):
        return None
    if not first or not current or frames[-1] != current or not _pair(first, current):
        return None
    return deepcopy(cast(dict[str, Any], current["parsed"]))


def title_stakes_comment(evidence: dict[str, Any]) -> str:
    candidate = evidence.get("candidate")
    if not candidate:
        return "Лимиты из заголовка неизвестны."
    limits = f"{candidate['small_blind']}/{candidate['big_blind']} р."
    text = (
        f"Лимиты {limits} подтверждены двумя кадрами."
        if evidence.get("status") == "confirmed"
        else f"Лимиты {limits} найдены в заголовке, подтверждения нет."
    )
    if candidate.get("bomb_pot_schedule_advertised"):
        text += " Стол допускает взрывной банк; тип текущей раздачи не подтверждён."
    return text


class TitleStakesConfirmation:
    def __init__(self) -> None:
        self.previous: dict[str, Any] | None = None

    def update(self, source: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
        sample = _sample(source, identity)
        capture = source.get("window_title_capture") or {}
        title = capture.get("after") if isinstance(capture, dict) else None
        parsed = parse_title_stakes(title if title is not None else source.get("window"))
        result: dict[str, Any] = {
            "schema_version": "hud-title-stakes/1",
            "status": "unavailable",
            "candidate": parsed,
            "candidate_origin": "capture_title" if title is not None else "selected_window_title",
            "confirmation_frames": [],
            "ruleset_verified": False,
        }
        if sample:
            frames = (
                [self.previous, sample] if self.previous and _pair(self.previous, sample) else []
            )
            result.update(
                status="confirmed" if frames else "awaiting_second_capture",
                confirmation_frames=deepcopy(frames),
            )
        elif not capture:
            result["reason"] = "capture_title_missing"
        elif isinstance(capture, dict) and capture.get("before") != capture.get("after"):
            result["reason"] = "title_changed_during_capture"
        else:
            result["reason"] = "title_or_screen_identity_unverified"
        # Missing, duplicate, or disagreeing samples cannot bridge confirmation.
        if sample and self.previous and not _pair(self.previous, sample):
            old = self.previous["source"]
            if old["frame_id"] == source["frame_id"] or old["captured_at"] >= source["captured_at"]:
                sample = None
        self.previous = sample
        return result
