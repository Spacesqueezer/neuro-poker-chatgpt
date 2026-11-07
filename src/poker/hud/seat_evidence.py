"""Conservative, source-backed player facts for offline request audits."""

import math
import re
from datetime import datetime
from functools import lru_cache

import cv2
import numpy as np
import pytesseract

from poker.hud.decision_stream import money
from poker.hud.seat_occupancy import read_dim_status
from poker.hud.table_signals import polarity_currency_amount, read_roi


@lru_cache(maxsize=128)
def stack_pixels(shape, pixels):
    crop = np.frombuffer(pixels, np.uint8).reshape(shape)
    gray = cv2.resize(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), None, fx=4, fy=4)
    data = pytesseract.image_to_data(
        gray, config="--psm 7", output_type=pytesseract.Output.DICT, timeout=3
    )
    words = [
        {"text": t, "confidence": float(c)}
        for t, c in zip(data["text"], data["conf"], strict=True)
        if t.strip()
    ]
    text = " ".join(w["text"] for w in words)
    score = min((w["confidence"] for w in words), default=0)
    valid = re.fullmatch(r"(?:\d+|\d{1,3}(?: \d{3})+)(?:[.,]\d{1,2})?\s*[pр₽]\.?", text)
    original = {
        "text": text,
        "confidence": score,
        "words": words,
        "value": money(text) if valid and score >= 85 else None,
    }
    if original["value"] is not None:
        # A confident single-scale OCR error repeats on identical screenshots.
        # A second scale/polarity must not confidently contradict that amount.
        check = polarity_currency_amount(shape, pixels)
        conflicts = sorted(
            {
                r["value"]
                for r in check["readings"]
                if r.get("value") is not None and r["value"] != original["value"]
            }
        )
        if conflicts:
            return {
                **original,
                "value": None,
                "original": original,
                "rejection": "conflicting_stack_amounts",
                "crosscheck_evidence": check,
                "conflicting_values": conflicts,
            }
        return {**original, "crosscheck_evidence": check}
    if re.search(r"[+−-]\s*\d", text):
        return {**original, "rejection": "signed_amount_not_stack"}
    retry = polarity_currency_amount(shape, pixels)
    if any(re.search(r"[+−-]\s*\d", r["text"]) for r in retry["readings"]):
        return {
            **original,
            "retry_evidence": retry,
            "rejection": "signed_amount_not_stack",
        }
    if retry["value"] is None:
        gray_retry = retry
        retry = yellow_stack_amount(crop, number_words=words)
        retry["grayscale_evidence"] = gray_retry
        conflicts = [
            r["value"]
            for r in gray_retry["readings"]
            if r["value"] is not None and r["value"] != retry["value"]
        ]
        retry["conflicting_values"] = conflicts
        if conflicts:
            retry["value"] = None
    if retry["value"] is None:
        previous_retry = retry
        retry = red_stack_amount(crop)
        retry["previous_evidence"] = previous_retry
        prior_readings = previous_retry.get("readings", []) + previous_retry.get(
            "grayscale_evidence", {}
        ).get("readings", [])
        conflicts = [
            r["value"]
            for r in prior_readings
            if r.get("value") is not None and r["value"] != retry["value"]
        ]
        retry["conflicting_values"] = conflicts
        if conflicts:
            retry["value"] = None
    if retry["value"] is None:
        return {**original, "retry_evidence": retry}
    return {
        "value": retry["value"],
        "text": retry["readings"][0]["text"],
        "confidence": min(r["confidence"] for r in retry["readings"]),
        "words": [],
        "original": original,
        "retry_evidence": retry,
        "method": retry["method"],
    }


def red_stack_amount(crop):
    """Suppress green felt without cropping glyphs or forcing OCR to digits."""
    mask = cv2.inRange(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV), (15, 45, 60), (40, 255, 255))
    if cv2.countNonZero(mask) < 8:
        return {"value": None, "readings": [], "method": "no_yellow_stack_glyphs"}
    readings = []
    for inverted in (False, True):
        channel = crop[:, :, 2]
        view = cv2.resize(
            255 - channel if inverted else channel,
            None,
            fx=3,
            fy=3,
            interpolation=cv2.INTER_CUBIC,
        )
        data = pytesseract.image_to_data(
            view, config="--psm 7", output_type=pytesseract.Output.DICT, timeout=3
        )
        words = [
            (t, float(c)) for t, c in zip(data["text"], data["conf"], strict=True) if t.strip()
        ]
        text = " ".join(t for t, _ in words)
        score = min((c for _, c in words), default=0)
        valid = re.fullmatch(r"\d+(?:[.,]\d{1,2})?\s*[pр₽]\.?", text)
        readings.append(
            {
                "text": text,
                "confidence": score,
                "inverted": inverted,
                "value": money(text) if valid and score >= 85 else None,
            }
        )
    value = readings[0]["value"]
    return {
        "value": value if value is not None and value == readings[1]["value"] else None,
        "readings": readings,
        "method": "red_channel_polarity_agreement",
    }


def yellow_stack_amount(crop, *, number_words=()):
    """Use color only to locate text; recognize original antialiased pixels."""
    mask = cv2.inRange(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV), (15, 45, 60), (40, 255, 255))
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return {"value": None, "readings": [], "method": "no_yellow_stack_glyphs"}
    # Dim leading digits may lose yellow saturation against green felt.
    # Keep the full width: a color bbox can turn 344.48 into 4.48.
    left, top = 0, max(0, int(ys.min()) - 4)
    right = crop.shape[1]
    bottom = min(crop.shape[0], int(ys.max()) + 5)
    tight = crop[top:bottom, left:right]
    result = {
        **polarity_currency_amount(tight.shape, tight.tobytes()),
        "roi_relative_to_stack": [left, top, right - left, bottom - top],
        "method": "yellow_located_grayscale_agreement",
    }
    if result["value"] is not None:
        return result
    # A narrower currency crop is allowed only when the complete numeric token
    # was already read confidently from the full-width original image.
    numeric = [word for word in number_words if re.search(r"\d", word["text"])]
    word = numeric[0] if len(numeric) == 1 else None
    number = (
        money(word["text"])
        if word and word["confidence"] >= 85 and re.fullmatch(r"\d+(?:[.,]\d{1,2})?", word["text"])
        else None
    )
    values = {r["value"] for r in result["readings"] if r["value"] is not None}
    if number is not None:
        values.add(number)
    if len(values) != 1:
        return result
    expected = next(iter(values))
    left = max(0, int(xs.min()) - 4)
    right = min(crop.shape[1], int(xs.max()) + 5)
    narrow = crop[top:bottom, left:right]
    check = polarity_currency_amount(narrow.shape, narrow.tobytes())
    conflicts = [
        r["value"] for r in result["readings"] if r["value"] is not None and r["value"] != expected
    ]
    if check["value"] != expected or conflicts:
        return {**result, "narrow_evidence": check, "full_width_number": word}
    return {
        **check,
        "roi_relative_to_stack": [left, top, right - left, bottom - top],
        "full_width_number": word,
        "full_width_evidence": result,
        "method": "full_width_number_and_tight_currency_agree",
    }


def read_stack(frame, roi, *, read_status=True):
    x, y, w, h = roi
    top = y + round(h * 0.54) - max(3, round(h * 0.04))
    box = [x + 3, top, w - 6, y + h - top]
    bx, by, bw, bh = box
    if (
        bx < 0
        or by < 0
        or bx + bw > frame.shape[1]
        or by + bh > frame.shape[0]
        or bw <= 0
        or bh <= 0
    ):
        return {"value": None, "roi": box, "error": "stack_roi_outside_image"}
    crop = frame[by : by + bh, bx : bx + bw]
    result = {**stack_pixels(crop.shape, crop.tobytes()), "roi": box}
    if not read_status:
        return result
    if result["value"] is None:
        status = read_roi(
            frame, (x + round(w * 0.14), y + round(h * 0.5), round(w * 0.72), round(h * 0.42))
        )
        if (
            status["text"].casefold().strip() == "вне игры"
            and status["words"]
            and min(word["confidence"] for word in status["words"]) >= 85
        ):
            result["seat_status"] = {"status": "sitting_out", **status}
    if result["value"] is None and "seat_status" not in result:
        dim = read_dim_status(frame, roi)
        if dim is not None:
            result["seat_status"] = dim
    return result


class ConfirmedStacks:
    def __init__(self):
        self.key = None
        self.samples = {}
        self.last = None

    def update(self, row, readings):
        at = datetime.fromisoformat(row["captured_at"])
        if self.last and (at <= self.last[0] or row["frame_id"] == self.last[1]):
            return {}
        self.last = at, row["frame_id"]
        identity = row["context"].get("hand_id", {})
        hand = str(identity.get("value", ""))
        key = (
            hand,
            row.get("window"),
            tuple(row.get("client_rect", [])),
            row.get("evidence_epoch"),
        )
        if (
            key != self.key
            or identity.get("confidence", 0) < 80
            or not re.fullmatch(r"\d{8,14}", hand)
        ):
            self.key, self.samples = key, {}
        if identity.get("confidence", 0) < 80 or not re.fullmatch(r"\d{8,14}", hand):
            return {}
        result = {}
        for seat, reading in readings.items():
            value = reading.get("value")
            old = self.samples.get(seat)
            source = {
                "frame_id": row["frame_id"],
                "captured_at": row["captured_at"],
                "image": row.get("image"),
                "evidence_epoch": row.get("evidence_epoch"),
                "reading": reading,
            }
            valid = (
                type(value) in (int, float)
                and math.isfinite(value)
                and value >= 0
                and reading.get("confidence", 0) >= 85
            )
            if not valid:
                self.samples.pop(seat, None)
                continue
            if (
                old
                and old[0] == value
                and old[1]["reading"].get("roi") == reading.get("roi")
                and old[1]["frame_id"] != source["frame_id"]
                and 0 < (at - datetime.fromisoformat(old[1]["captured_at"])).total_seconds() <= 5
            ):
                result[seat] = {"value": value, "confirmation_frames": [old[1], source]}
            self.samples[seat] = value, source
        for seat in self.samples.keys() - readings.keys():
            self.samples.pop(seat, None)
        return result


def confirmed_bets(row, previous, tracker):
    """Confirm the visible street contribution on two consecutive source images."""
    if not previous or tracker.current is None or tracker.street is None:
        return {}
    if tracker.source.get("frame_id") != row["frame_id"]:
        return {}
    elapsed = (
        datetime.fromisoformat(row["captured_at"]) - datetime.fromisoformat(previous["captured_at"])
    ).total_seconds()
    if not 0 < elapsed <= 5 or row["frame_id"] == previous["frame_id"]:
        return {}
    if any(row.get(key) != previous.get(key) for key in ("window", "client_rect")):
        return {}
    for source in (previous, row):
        identity = source["context"].get("hand_id", {})
        if (
            identity.get("value") != tracker.current["hand_id"]
            or identity.get("confidence", 0) < 80
        ):
            return {}
    if row["context"].get("decision_hand", {}).get("board") != previous["context"].get(
        "decision_hand", {}
    ).get("board"):
        return {}
    readings = []
    for source in (previous, row):
        slots = source["context"].get("table_signals", {}).get("slots", [])
        if [s.get("seat_index") for s in slots] != list(range(7)):
            return {}
        readings.append({s["seat_index"]: s for s in slots})
    result = {}
    for seat, current in readings[1].items():
        old = readings[0][seat]
        value = current.get("current_bet")
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            continue
        if (
            type(old.get("current_bet")) not in (int, float)
            or old.get("roi") != current.get("roi")
            or old.get("current_bet") != value
        ):
            continue
        if any(
            s.get("settlement_label") or s.get("bet_evidence", {}).get("value") != value
            for s in (old, current)
        ):
            continue
        result[seat] = {
            "value": value,
            "street": tracker.street,
            "hand_id": tracker.current["hand_id"],
            "confirmation_frames": [
                {
                    **{k: source[k] for k in ("frame_id", "captured_at", "image")},
                    "reading": slot["bet_evidence"],
                }
                for source, slot in ((previous, old), (row, current))
            ],
            "semantics": "visible_street_contribution_not_action_size",
        }
    return result


def participation(tracker):
    hand = tracker.current
    if not hand:
        return {}
    result = {}
    for seat, participant in hand["participants"].items():
        if not any(
            e["kind"] in {"repeated_card_backs", "repeated_hero_cards"}
            for e in participant["evidence"]
        ):
            continue  # A lingering label alone must not prove cards in a new hand.
        index = int(seat)
        kind, sources = tracker.presence.get(index, (None, []))
        folded = participant["fold_observed"]
        conflict = "action_after_fold" in hand["warnings"]
        result[index] = {
            "cards_dealt": True,
            "is_active": None
            if conflict
            else False
            if folded
            else True
            if kind and len(sources) == 2
            else None,
            "evidence": participant["evidence"],
        }
    return result


def occupancy_evidence(participant_facts, stack_facts, stack_readings):
    result = {}
    active = {seat for seat, fact in participant_facts.items() if fact["is_active"] is True}
    for seat in active | set(stack_facts):
        result[seat] = {
            "occupied": True,
            "basis": "confirmed_cards" if seat in active else "confirmed_stack",
        }
    for seat, reading in stack_readings.items():
        status = reading.get("seat_status") or {}
        words = status.get("words", [])
        if status.get("status") == "sitting_out" and (
            (words and min(word["confidence"] for word in words) >= 85)
            or (
                status.get("method") == "visual_template"
                and status.get("similarity", 0) >= 0.96
                and status.get("detail_contrast", 0) >= 3
            )
        ):
            result[seat] = {
                "occupied": True,
                "basis": "explicit_sitting_out_label",
                "seat_status": status,
            }
    return result
