"""Read and confirm visible wager controls; no inferred legal betting bounds."""

import re
from datetime import datetime

import cv2
import numpy as np

from poker.hud.decision_stream import money
from poker.hud.table_signals import numeric_words, polarity_currency_amount


class EndpointConfirmation:
    """Confirm a current visual endpoint twice; never carry bounds into later frames."""

    def __init__(self):
        self.previous = None

    def update(self, row, identity, evidence):
        previous, self.previous = self.previous, None
        selected = row["controls"].get("selected_wager")
        amount = (evidence.get("field") or {}).get("value")
        endpoint = evidence.get("endpoint")
        if (
            not row["controls"].get("flags")
            or endpoint not in ("left", "right")
            or not selected
            or amount is None
            or amount != selected["value"]
            or identity.get("confidence", 0) < 80
            or not re.fullmatch(r"\d{8,14}", str(identity.get("value", "")))
        ):
            return None
        if row["controls"].get("call_amount") is None:
            return None
        if not row.get("window") or len(row.get("client_rect") or []) != 4:
            return None
        key = (
            identity["value"],
            row.get("window"),
            tuple(row.get("client_rect") or []),
            tuple(row.get("board_cards", ())),
            row.get("evidence_epoch"),
            endpoint,
            amount,
            selected["action"],
            row["controls"]["call_amount"],
        )
        captured = datetime.fromisoformat(row["captured_at"])
        source = {k: row[k] for k in ("frame_id", "captured_at", "image")}
        self.previous = key, captured, source
        if previous:
            old_key, old_at, old_source = previous
            if (
                key == old_key
                and old_source["frame_id"] != source["frame_id"]
                and 0 < (captured - old_at).total_seconds() <= 2.5
            ):
                return {
                    "hand_id": identity["value"],
                    "endpoint": endpoint,
                    "value": amount,
                    "confirmation_frames": [old_source, source],
                    "legal_bound_confirmed": False,
                }
        return None


def read_field_view(view):
    scaled = cv2.resize(view, None, fx=3, fy=3)
    words = numeric_words(scaled.shape, scaled.tobytes(), "--psm 7")
    text = " ".join(t for t, _ in words)
    score = min((c for _, c in words), default=0)
    valid = re.fullmatch(r"\d+(?:[.,]\d{1,2})?(?:\s*[pр₽]\.?)?", text)
    return {
        "text": text,
        "confidence": score,
        "value": money(text) if valid and score >= 85 else None,
    }


def remove_field_caret(mask):
    """Remove only a rightmost thin stroke substantially taller than every digit."""
    components = cv2.connectedComponentsWithStats(mask)[2][1:]
    candidates = []
    for x, y, w, h, area in components:
        others = [c for c in components if c[0] + c[2] <= x and c[3] > mask.shape[0] * 0.2]
        if (
            len(others) >= 1
            and h > mask.shape[0] * 0.5
            and w <= h * 0.08
            and area > w * h * 0.9
            and all(c[0] <= x for c in components)
            and h > max(c[3] for c in others) * 1.4
        ):
            candidates.append([int(x), int(y), int(w), int(h)])
    clean = mask.copy()
    if len(candidates) == 1:
        x, y, w, h = candidates[0]
        clean[y : y + h, x : x + w] = 0
        return clean, candidates[0]
    return clean, None


def read_field(crop):
    original = read_field_view(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY))
    result = {**original}
    if original["value"] is not None:
        return result
    # A caret is geometry, not a character to silently strip from arbitrary OCR.
    # Read the original antialiased pixels before trying lossy binary masks.
    mask = cv2.inRange(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV), (0, 0, 150), (179, 65, 255))
    _, caret = remove_field_caret(mask)
    if caret and re.fullmatch(r"\d+(?:[.,]\d{1,2})?\s*\|?", original["text"]):
        x, _, _, _ = caret
        gray = cv2.cvtColor(crop[:, :x], cv2.COLOR_BGR2GRAY)
        readings = [read_field_view(gray), read_field_view(255 - gray)]
        value = readings[0]["value"]
        result["caret_evidence"] = {"roi": caret, "readings": readings}
        if (
            value is not None
            and readings[1]["value"] == value
            and (original["confidence"] >= 85 or min(r["confidence"] for r in readings) >= 95)
            and money(original["text"].rstrip("| ")) == value
        ):
            result.update(
                value=value,
                confidence=min(original["confidence"], *(r["confidence"] for r in readings)),
                text=readings[0]["text"],
                original=original,
                method="geometric_caret_original_polarities_agree",
            )
            return result
    checks = []
    for threshold in (150, 175):
        mask = cv2.inRange(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV), (0, 0, threshold), (179, 65, 255))
        clean, caret = remove_field_caret(mask)
        checks.append({**read_field_view(255 - clean), "threshold": threshold, "caret_roi": caret})
    result["original"] = original
    result["mask_checks"] = checks
    if checks[0]["value"] is not None and checks[0]["value"] == checks[1]["value"]:
        result.update(
            value=checks[0]["value"],
            confidence=min(c["confidence"] for c in checks),
            text=checks[0]["text"],
            method="two_glyph_masks_agree",
        )
    if result["value"] is None:
        # Keep every bright glyph, including punctuation; do not crop a numeric
        # component alone and accidentally discard a decimal separator.
        mask = cv2.inRange(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV), (0, 0, 150), (179, 65, 255))
        ys, xs = np.nonzero(mask)
        if len(xs):
            left, top = max(0, int(xs.min()) - 2), max(0, int(ys.min()) - 2)
            right, bottom = (
                min(crop.shape[1], int(xs.max()) + 3),
                min(crop.shape[0], int(ys.max()) + 3),
            )
            tight = crop[top:bottom, left:right]
            reading = {
                **polarity_currency_amount(tight.shape, tight.tobytes()),
                "roi_relative_to_crop": [left, top, right - left, bottom - top],
            }
            value = reading["value"]
            conflicts = [
                c["value"] for c in checks if c["value"] is not None and c["value"] != value
            ]
            reading["conflicting_values"] = conflicts
            result["tight_evidence"] = reading
            if value is not None and not conflicts:
                result.update(
                    value=value,
                    confidence=min(r["confidence"] for r in reading["readings"]),
                    text=reading["readings"][0]["text"],
                    method="tight_currency_polarities_agree",
                )
    return result


def rail_geometry(frame, field, knob):
    """Locate the dark rail around the light knob, without inferring monetary bounds."""
    h, w = frame.shape[:2]
    kx, ky, kw, kh = knob["roi"]
    fx = field["roi"][0]
    left = round(w * 0.715)
    top, bottom = ky + round(kh * 0.3), ky + round(kh * 0.7)
    value = cv2.cvtColor(frame[top:bottom, left:fx], cv2.COLOR_BGR2HSV)[:, :, 2]
    dark = value < 38
    dark[:, max(0, kx - left - 1) : kx + kw - left + 1] = False
    columns = np.any(dark, axis=0)
    occupied = columns.copy()
    occupied[max(0, kx - left) : kx + kw - left] = True
    xs = np.flatnonzero(occupied)
    if not len(xs):
        return None
    a, b = int(xs[0] + left), int(xs[-1] + left + 1)
    # Reject clipped rails, background blobs, gaps, or a missing dark track.
    if not (0.11 < (b - a) / w < 0.18 and a > left + 2 and 1 < fx - b < kw * 0.4):
        return None
    if occupied[a - left : b - left].mean() < 0.97 or columns.sum() < (b - a - kw) * 0.9:
        return None
    if np.count_nonzero(dark) / max(1, columns.sum()) > kh * 0.3:
        return None
    travel = b - a - kw
    position = (kx - a) / travel
    endpoint = "left" if kx - a <= 2 else "right" if b - (kx + kw) <= 2 else "interior"
    return {
        "span": [a, b],
        "position": position,
        "endpoint": endpoint,
        "basis": "dark_rail_and_knob_extent",
        "legal_bound_confirmed": False,
    }


def field_and_knob(frame, *, read_amount=True):
    h, w = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    x0, y0 = round(w * 0.86), round(h * 0.94)
    mask = cv2.inRange(hsv[y0:, x0:], (0, 0, 0), (179, 255, 38))
    fields = []
    for contour in cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
        x, y, cw, ch = cv2.boundingRect(contour)
        if (
            0.10 < cw / w < 0.14
            and 0.035 < ch / h < 0.06
            and cv2.contourArea(contour) > cw * ch * 0.85
        ):
            fields.append((x + x0, y + y0, cw, ch))
    result = {"field": None, "knob": None, "endpoint": None}
    if len(fields) != 1:
        return result
    x, y, cw, ch = fields[0]
    crop = frame[y + 4 : y + ch - 4, x + 4 : x + cw - 4]
    result["field"] = {
        "roi": [x, y, cw, ch],
        **(read_field(crop) if read_amount else {"value": None}),
    }
    left = round(w * 0.715)
    mask = cv2.inRange(hsv[y : y + ch, left:x], (0, 0, 130), (179, 65, 255))
    knobs = []
    for contour in cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
        kx, ky, kw, kh = cv2.boundingRect(contour)
        if (
            0.01 < kw / w < 0.035
            and 0.012 < kh / h < 0.05
            and 0.8 < kw / kh < 1.2
            and cv2.contourArea(contour) > kw * kh * 0.6
        ):
            knobs.append(
                {
                    "roi": [left + kx, y + ky, kw, kh],
                    "center_x_normalized": (left + kx + kw / 2) / w,
                }
            )
    if len(knobs) == 1:
        result["knob"] = knobs[0]
        rail = rail_geometry(frame, result["field"], knobs[0])
        result["rail"] = rail
        if rail:
            result["endpoint"] = rail["endpoint"]
    return result
