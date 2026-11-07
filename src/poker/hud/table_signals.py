"""Frame-local table facts with explicit evidence; no betting-rule inference."""

import csv
import io
import math
import re
import subprocess
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
import pytesseract

from poker.hud.bet_visibility import bet_visibility
from poker.hud.card_backs import card_back_pair
from poker.hud.decision_stream import money
from poker.hud.recognition import layout_panels

TESSDATA = Path(__file__).resolve().parents[3] / "data/hud/tessdata"
DEALER_ANCHOR_OFFSETS = (
    (0.65, 0.5),
    (-0.65, 0.5),
    (0.72, -0.3),
    (-0.72, -0.3),
    (0.25, -3.05),
    (-0.25, -3.05),
    (0.55, -2.7),
)


@lru_cache(maxsize=256)
def read_text(shape, pixels, white=False):
    crop = np.frombuffer(pixels, np.uint8).reshape(shape)
    if not (TESSDATA / "rus.traineddata").exists():
        return {"text": "", "words": [], "error": "rus_ocr_not_installed"}
    if white in ("colored", "dim_colored"):
        crop = 255 - cv2.inRange(
            cv2.cvtColor(crop, cv2.COLOR_BGR2HSV),
            (0, 110, 130) if white == "colored" else (0, 80, 65),
            (179, 255, 255),
        )
    elif white:
        crop = 255 - cv2.inRange(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV), (0, 0, 175), (179, 95, 255))
    crop = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    ok, encoded = cv2.imencode(".png", crop)
    if not ok:
        raise ValueError("Cannot encode OCR crop")
    # An argument list preserves Windows paths with spaces without shlex quoting.
    result = subprocess.run(
        [
            pytesseract.pytesseract.tesseract_cmd,
            "stdin",
            "stdout",
            "-l",
            "rus",
            "--psm",
            "6",
            "--tessdata-dir",
            str(TESSDATA),
            "-c",
            "tessedit_create_tsv=1",
        ],
        input=encoded.tobytes(),
        capture_output=True,
        timeout=3,
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    data = csv.DictReader(io.StringIO(result.stdout.decode("utf-8")), delimiter="\t")
    words = [
        {
            "text": row["text"],
            "confidence": float(row["conf"]),
            "roi": [round(int(row[k]) / 3) for k in ("left", "top", "width", "height")],
        }
        for row in data
        if row.get("text", "").strip()
    ]
    return {"text": " ".join(w["text"] for w in words), "words": words}


def read_roi(frame, roi, white=False):
    x, y, w, h = map(int, roi)
    crop = frame[max(0, y) : y + h, max(0, x) : x + w]
    if not crop.size:
        return {"text": "", "words": [], "roi": list(roi)}
    return {**read_text(crop.shape, crop.tobytes(), white), "roi": list(roi)}


def controls(frame):
    """Only colored live action buttons, never grey pre-action checkboxes."""
    h, w = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    bands = [(38, 85), (12, 37), (0, 10)]
    buttons = []
    for lo, hi in bands:
        mask = cv2.inRange(hsv, (lo, 120, 100), (hi, 255, 255))
        if lo == 0:
            mask |= cv2.inRange(hsv, (165, 120, 100), (179, 255, 255))
        mask[: round(h * 0.88)] = 0
        mask[:, : round(w * 0.25)] = 0
        mask[:, round(w * 0.74) :] = 0
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        found = []
        for contour in contours:
            x, y, cw, ch = cv2.boundingRect(contour)
            if (
                0.08 < cw / w < 0.2
                and 0.045 < ch / h < 0.13
                and cv2.contourArea(contour) > cw * ch * 0.65
            ):
                found.append((x, y, cw, ch))
        if len(found) == 1:
            x, y, cw, ch = found[0]
            buttons.append(read_roi(frame, (x + 4, y + 4, cw - 8, ch - 8), True))
    names = {
        "сбросить": "fold",
        "чек": "check",
        "колл": "call",
        "уравнять": "call",
        "поставить": "bet",
        "повысить": "raise",
        "поднять": "raise",
        "рейз": "raise",
        "ва-банк": "all_in",
    }
    actions = {}
    for button in buttons:
        for word in button["words"]:
            name = names.get(word["text"].casefold().strip(" .:"))
            if name and word["confidence"] >= 85:
                actions[name] = button
    flags = {}
    if len(buttons) == 3 and "fold" in actions and ("check" in actions) != ("call" in actions):
        flags = {"can_fold": True, "can_check": "check" in actions, "can_call": "call" in actions}
        if ("bet" in actions) != ("raise" in actions):
            flags.update(can_bet="bet" in actions, can_raise="raise" in actions)
        if "all_in" in actions and not ({"bet", "raise"} & actions.keys()):
            flags["can_all_in"] = True
    call = 0.0 if flags.get("can_check") else None
    if flags.get("can_call"):
        button = actions["call"]
        values = []
        for word in button["words"]:
            if not re.fullmatch(r"\d+(?:[.,]\d{1,2})?", word["text"]):
                continue
            reading = button_number(frame, button["roi"], word)
            button["number_evidence"] = reading
            if reading["confidence"] >= 85 and reading["value"] == money(word["text"]):
                values.append(reading["value"])
        if not values:
            # OCR can join a misread digit and currency, e.g. "Зр.".
            # Read the pixels again; never replace the letter with a presumed digit.
            for word in button["words"]:
                # A currency glyph may itself become a digit: "3 р." -> "32.".
                # The retry must still read an explicit currency from the pixels.
                if not re.fullmatch(r"(?:[^\s]+[pр₽]\.?|\d+\.)", word["text"]):
                    continue
                bx, by, bw, bh = button["roi"]
                x, y, w, h = word["roi"]
                left, top = max(bx, bx + x - 4), max(by, by + y - 4)
                right, bottom = min(bx + bw, bx + x + w + 4), min(by + bh, by + y + h + 4)
                crop = frame[top:bottom, left:right]
                if crop.size:
                    check = {
                        **grayscale_amount(crop.shape, crop.tobytes()),
                        "roi": [left, top, right - left, bottom - top],
                    }
                    recovered = check["value"]
                    if recovered is None:
                        retry = small_currency_amount(crop.shape, crop.tobytes())
                        check["small_scale_evidence"] = retry
                        recovered = retry["value"]
                        if recovered is None:
                            recovered = confirm_fused_currency(word, retry["readings"])
                            check["fused_word_agreement"] = recovered
                        if recovered is None:
                            polarity = {**polarity_currency_amount(crop.shape, crop.tobytes())}
                            check["polarity_evidence"] = polarity
                            candidate = polarity["value"]
                            prior = [check, *retry["readings"], button.get("number_evidence", {})]
                            if candidate is None:
                                native = polarity_currency_amount(
                                    crop.shape, crop.tobytes(), scale=1
                                )
                                check["native_polarity_evidence"] = native
                                prior.extend(polarity["readings"])
                                candidate = native["value"]
                            prior.extend(
                                {"value": money(w["text"]), "confidence": w.get("confidence", 0)}
                                for w in button["words"]
                            )
                            conflicts = [
                                r["value"]
                                for r in prior
                                if r.get("confidence", 0) >= 85
                                and r.get("value") is not None
                                and r["value"] != candidate
                            ]
                            polarity["conflicting_values"] = conflicts
                            if not conflicts:
                                recovered = candidate
                    button["currency_number_evidence"] = check
                    if recovered is not None:
                        values.append(recovered)
        if len(values) == 1:
            call = values[0]
        elif not values:
            bx, by, bw, bh = button["roi"]
            left, top = bx + round(bw * 0.16), by + round(bh * 0.48)
            right, bottom = bx + round(bw * 0.84), by + round(bh * 0.91)
            crop = frame[top:bottom, left:right]
            if crop.size:
                reading = currency_line(crop.shape, crop.tobytes())
                button["full_line_evidence"] = {
                    **reading,
                    "roi": [left, top, right - left, bottom - top],
                }
                call = corroborated_line_value(button)
                if call is None:
                    retry = {**selected_currency_amount(crop.shape, crop.tobytes())}
                    value = corroborated_line_value({**button, "full_line_evidence": retry})
                    conflicts = [
                        r["value"]
                        for r in reading["readings"]
                        if r["value"] is not None and value is not None and r["value"] != value
                    ]
                    retry["prior_line_conflicts"] = conflicts
                    button["currency_recovery_evidence"] = retry
                    if not conflicts:
                        call = value
    selected = None
    for action in ("bet", "raise", "all_in"):
        if flags.get("can_" + action):
            button = actions[action]
            amounts = []
            for word in button["words"]:
                if re.fullmatch(r"\d+(?:[.,]\d{1,2})?", word["text"]):
                    check = button_number(frame, button["roi"], word)
                    button["selected_number_evidence"] = check
                    if check["confidence"] >= 85 and check["value"] == money(word["text"]):
                        amounts.append(check["value"])
            if not amounts:
                bx, by, bw, bh = button["roi"]
                left, top = bx + round(bw * 0.16), by + round(bh * 0.48)
                right, bottom = bx + round(bw * 0.84), by + round(bh * 0.91)
                crop = frame[top:bottom, left:right]
                if crop.size:
                    reading = {
                        **selected_currency_amount(crop.shape, crop.tobytes()),
                        "roi": [left, top, right - left, bottom - top],
                    }
                    button["selected_currency_evidence"] = reading
                    recovered = corroborated_line_value(
                        {
                            "words": button["words"],
                            "number_evidence": button.get("selected_number_evidence", {}),
                            "full_line_evidence": reading,
                        }
                    )
                    if recovered is not None:
                        amounts.append(recovered)
            if len(amounts) == 1:
                selected = {
                    "action": action,
                    "value": amounts[0],
                    "semantics": "selected_button_amount_not_legal_bound",
                }
    return {
        "buttons": buttons,
        "flags": flags,
        "call_amount": call,
        "selected_wager": selected,
        "min_raise_amount": None,
        "max_raise_amount": None,
        "raise_bounds_reason": "legal_bounds_not_observed",
    }


@lru_cache(maxsize=128)
def numeric_words(shape, pixels, config):
    """Reuse OCR for identical prepared pixels, never a decision or frame provenance."""
    data = pytesseract.image_to_data(
        np.frombuffer(pixels, np.uint8).reshape(shape),
        config=config,
        output_type=pytesseract.Output.DICT,
        timeout=3,
    )
    return tuple(
        (t, float(c)) for t, c in zip(data["text"], data["conf"], strict=True) if t.strip()
    )


def button_number(frame, button_roi, word):
    bx, by, _, _ = button_roi
    x, y, w, h = word["roi"]
    crop = frame[by + y : by + y + h, bx + x : bx + x + w]
    mask = 255 - cv2.inRange(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV), (0, 0, 175), (179, 95, 255))
    mask = cv2.resize(mask, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
    mask = cv2.copyMakeBorder(mask, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=255)
    words = numeric_words(
        mask.shape, mask.tobytes(), "--psm 13 -c tessedit_char_whitelist=0123456789.,"
    )
    readings = [(money(t), float(c)) for t, c in words if re.fullmatch(r"\d+(?:[.,]\d{1,2})?", t)]
    value, confidence = max(readings, key=lambda r: r[1], default=(None, 0))
    result = {"value": value, "confidence": confidence, "roi": [bx + x, by + y, w, h]}
    expected = money(word["text"])
    if (
        (confidence < 85 or value != expected)
        and expected is not None
        and word.get("confidence", 0) >= 85
    ):
        _, _, bw, bh = button_roi
        left, top = max(bx, bx + x - 4), max(by, by + y - 4)
        right, bottom = min(bx + bw, bx + x + w + 4), min(by + bh, by + y + h + 4)
        padded = frame[top:bottom, left:right]
        if padded.size:
            gray = cv2.resize(cv2.cvtColor(padded, cv2.COLOR_BGR2GRAY), None, fx=4, fy=4)
            words = numeric_words(gray.shape, gray.tobytes(), "--psm 7")
            text = " ".join(t for t, _ in words)
            score = min((c for _, c in words), default=0)
            parsed = money(text) if re.fullmatch(r"\d+(?:[.,]\d{1,2})?", text) else None
            result["grayscale_check"] = {
                "text": text,
                "confidence": score,
                "value": parsed,
                "roi": [left, top, right - left, bottom - top],
            }
            if score >= 85 and parsed == expected:
                result.update(value=parsed, confidence=score, method="padded_grayscale_agreement")
    return result


@lru_cache(maxsize=128)
def selected_currency_amount(shape, pixels):
    """Recover a complete currency line, preserving every earlier OCR reading."""
    original = polarity_currency_amount(shape, pixels)
    if original["value"] is not None:
        return original
    crop = np.frombuffer(pixels, np.uint8).reshape(shape)
    mask = cv2.inRange(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV), (0, 0, 175), (179, 95, 255))
    ys, xs = np.nonzero(mask)
    attempts = [original]
    if len(xs):
        left, top = max(0, int(xs.min()) - 2), max(0, int(ys.min()) - 2)
        right, bottom = min(shape[1], int(xs.max()) + 3), min(shape[0], int(ys.max()) + 3)
        tight = crop[top:bottom, left:right]
        binary = cv2.cvtColor(255 - mask, cv2.COLOR_GRAY2BGR)
        views = [
            ("white_mask", binary),
            ("tight_gray", tight),
            ("tight_scales", tight),
        ]
        start = currency_row_start(mask)
        if start is not None and not any(
            re.search(r"[+−-]\s*\d", r["text"]) for r in original["readings"]
        ):
            views.append(("separate_currency_row", crop[start:]))
            views.append(("separate_currency_row_native", crop[start:]))
        for method, view in views:
            reader = currency_line if method == "tight_scales" else polarity_currency_amount
            reading = {
                **(
                    polarity_currency_amount(view.shape, view.tobytes(), scale=1)
                    if method == "separate_currency_row_native"
                    else reader(view.shape, view.tobytes())
                ),
                "preprocessing": method,
            }
            attempts.append(reading)
            candidate = reading["value"]
            if candidate is None:
                continue
            conflicts = [
                r["value"]
                for attempt in attempts
                for r in attempt["readings"]
                if r.get("value") is not None and r["value"] != candidate
            ]
            return {
                "value": candidate if not conflicts else None,
                "attempts": attempts,
                "conflicting_values": conflicts,
                "method": "selected_currency_recovery",
            }
    return {"value": None, "attempts": attempts, "method": "selected_currency_recovery"}


def currency_row_start(mask):
    """Separate a clipped upper caption from an intact lower amount line."""
    rows = np.flatnonzero(np.any(mask, axis=1))
    if len(rows) < 3 or rows[0] != 0:
        return None
    gaps = np.flatnonzero(np.diff(rows) >= 3)
    if len(gaps) != 1:
        return None
    index = int(gaps[0])
    upper, lower = int(rows[index]), int(rows[index + 1])
    if upper + 1 > mask.shape[0] * 0.1 or rows[-1] - lower < mask.shape[0] * 0.4:
        return None
    return (upper + lower + 1) // 2


def corroborated_line_value(button):
    reading = button["full_line_evidence"]
    value = reading["value"]
    reliable = [
        money(word["text"])
        for word in button["words"]
        if word.get("confidence", 0) >= 85
        and re.fullmatch(r"\d+(?:[.,]\d{1,2})?(?:\s*[pр₽]\.?)?", word["text"])
    ]
    numeric = button.get("number_evidence", {})
    if numeric.get("confidence", 0) >= 85 and numeric.get("value") is not None:
        reliable.append(numeric["value"])
    conflicts = [amount for amount in reliable if value is not None and amount != value]
    reading["conflicting_values"] = conflicts
    return None if conflicts else value


@lru_cache(maxsize=128)
def currency_line(shape, pixels):
    """Keep decimals and currency together; require two complete OCR readings."""
    crop = np.frombuffer(pixels, np.uint8).reshape(shape)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    readings = []
    for scale in (2, 3):
        view = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
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
                "scale": scale,
                "value": money(text) if valid and score >= 85 else None,
            }
        )
    value = readings[0]["value"]
    return {
        "value": value if value is not None and value == readings[1]["value"] else None,
        "readings": readings,
        "method": "full_currency_line_two_scales",
    }


@lru_cache(maxsize=128)
def english_amount(shape, pixels):
    crop = np.frombuffer(pixels, np.uint8).reshape(shape)
    mask = 255 - cv2.inRange(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV), (0, 0, 175), (179, 95, 255))
    mask = cv2.resize(mask, None, fx=3, fy=3)
    data = pytesseract.image_to_data(
        mask, config="--psm 7", output_type=pytesseract.Output.DICT, timeout=3
    )
    words = [(t, float(c)) for t, c in zip(data["text"], data["conf"], strict=True) if t.strip()]
    text = " ".join(t for t, _ in words)
    score = min((c for _, c in words), default=0)
    value = money(text) if score >= 85 and re.search(r"[pр₽]\.?$", text) else None
    return {"text": text, "confidence": score, "value": value}


@lru_cache(maxsize=128)
def small_currency_amount(shape, pixels):
    """Require agreement of gray and white-glyph OCR at the smaller scale."""
    crop = np.frombuffer(pixels, np.uint8).reshape(shape)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    white = 255 - cv2.inRange(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV), (0, 0, 175), (179, 95, 255))
    readings = []
    for view in (gray, white):
        view = cv2.resize(view, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
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
                "value": money(text) if valid and score >= 85 else None,
            }
        )
    value = readings[0]["value"]
    return {
        "value": value if value is not None and value == readings[1]["value"] else None,
        "readings": readings,
        "method": "two_scale2_views_agree",
    }


@lru_cache(maxsize=128)
def polarity_currency_amount(shape, pixels, *, scale=2):
    """Read antialiased small currency text in both grayscale polarities."""
    crop = np.frombuffer(pixels, np.uint8).reshape(shape)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    readings = []
    for inverted in (False, True):
        view = cv2.resize(
            255 - gray if inverted else gray,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_LINEAR,
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
        "method": "grayscale_polarity_agreement",
        "scale": scale,
    }


def confirm_fused_currency(word, readings):
    """A numeric currency word can corroborate a separate high-confidence pixel read."""
    if word.get("confidence", 0) < 80 or not re.fullmatch(
        r"\d+(?:[.,]\d{1,2})?\s*[pр₽]\.?", word.get("text", "")
    ):
        return None
    expected = money(word["text"])
    reliable = [
        r["value"] for r in readings if r.get("confidence", 0) >= 85 and r.get("value") is not None
    ]
    return expected if reliable and all(value == expected for value in reliable) else None


@lru_cache(maxsize=128)
def grayscale_amount(shape, pixels):
    """Retain antialiased strokes that a white-pixel mask can remove."""
    crop = np.frombuffer(pixels, np.uint8).reshape(shape)
    gray = cv2.resize(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), None, fx=4, fy=4)
    data = pytesseract.image_to_data(
        gray, config="--psm 7", output_type=pytesseract.Output.DICT, timeout=3
    )
    words = [(t, float(c)) for t, c in zip(data["text"], data["conf"], strict=True) if t.strip()]
    text = " ".join(t for t, _ in words)
    score = min((c for _, c in words), default=0)
    # No character whitelist or substitution of letters with expected blind values.
    valid = re.fullmatch(r"\s*\d+(?:[.,]\d{1,2})?\s*[pр₽]\.?\s*", text)
    return {
        "text": text,
        "confidence": score,
        "value": money(text) if valid and score >= 85 else None,
    }


def recover_amount(frame, bet):
    """Retry an unknown currency-bearing label, preserving the original OCR evidence."""
    if bet.get("value") is not None:
        return bet
    readings = [bet, bet.get("alternative", {})]
    if not any(re.search(r"[pр₽]\.?$", r.get("text", "").strip()) for r in readings):
        return bet
    if not bet.get("roi"):
        return bet
    x, y, w, h = bet["roi"]
    pad = max(4, round(h * 0.125))
    top, bottom = max(0, y - pad), min(frame.shape[0], y + h + pad)
    left, right = max(0, x), min(frame.shape[1], x + w)
    crop = frame[top:bottom, left:right]
    if not crop.size:
        return bet
    check = {
        **grayscale_amount(crop.shape, crop.tobytes()),
        "roi": [left, top, right - left, bottom - top],
    }
    return {**bet, "value": check["value"], "grayscale_evidence": check}


def pot(frame, regions):
    region = regions.get("table_text", {})
    words = region.get("words", [])
    for index, word in enumerate(words[:-1]):
        if word["text"].casefold().rstrip(":") not in {"bank", "банк"}:
            continue
        x, y, w, h = word["roi"]
        nx, ny, nw, nh = words[index + 1]["roi"]
        if abs(y - ny) > max(h, nh) * 0.5:
            continue
        rx, ry, _, _ = region["roi"]
        reading = read_roi(
            frame, (rx + x - 3, ry + min(y, ny) - 3, nx + nw - x + max(25, h * 2), max(h, nh) + 6)
        )
        values = [
            money(w["text"])
            for w in reading["words"]
            if w["confidence"] >= 85 and re.fullmatch(r"\d+(?:[.,]\d{1,2})?", w["text"])
        ]
        anchor = any(
            w["text"].casefold().rstrip(":") == "банк" and w["confidence"] >= 85
            for w in reading["words"]
        )
        primary = {"value": values[0] if anchor and len(values) == 1 else None, **reading}
        if primary["value"] is not None or re.search(r"[+−-]\s*\d", reading["text"]):
            return primary
        fallback = anchored_pot(frame)
        candidate = fallback["value"]
        if candidate is not None and all(value == candidate for value in values):
            return {**fallback, "primary_evidence": primary}
        return {**primary, "fallback_evidence": fallback}
    return anchored_pot(frame)


def anchored_pot(frame):
    """Locate the green pot caption, then read its original pixels twice."""
    h, w = frame.shape[:2]
    x, y = round(w * 0.4), round(h * 0.34)
    region = frame[y : round(h * 0.39), x : round(w * 0.6)]
    empty = {"value": None, "text": "", "words": []}
    if not region.size:
        return empty
    mask = cv2.inRange(cv2.cvtColor(region, cv2.COLOR_BGR2HSV), (35, 100, 170), (95, 255, 255))
    ys, xs = np.nonzero(mask)
    if len(xs) < 12:
        return empty
    left, top = max(0, int(xs.min()) - 3), max(0, int(ys.min()) - 3)
    right, bottom = min(region.shape[1], int(xs.max()) + 4), min(region.shape[0], int(ys.max()) + 4)
    crop = region[top:bottom, left:right]
    readings = []
    for inverted in (False, True):
        view = 255 - crop if inverted else crop
        reading = read_text(view.shape, view.tobytes())
        match = re.fullmatch(r"Банк:\s*(\d+(?:[.,]\d{1,2})?)\s*[рp₽]\.?", reading["text"], re.I)
        score = min((word["confidence"] for word in reading["words"]), default=0)
        readings.append(
            {
                **reading,
                "inverted": inverted,
                "value": money(match[1]) if match and score >= 85 else None,
            }
        )
    value = readings[0]["value"]
    return {
        **readings[0],
        "value": value if value is not None and value == readings[1]["value"] else None,
        "roi": [x + left, y + top, right - left, bottom - top],
        "method": "green_pot_original_polarities",
        "readings": readings,
    }


def cross_roi_currency_consensus(attempts, original_roi, prior_values=()):
    """Require full-width support and both polarities across distinct regions."""
    if any(
        re.search(r"[+−—-]\s*\d", r.get("text", ""))
        for attempt in attempts
        for r in attempt.get("readings", [])
    ):
        return None
    support = [
        {**r, "roi": a["roi"]}
        for a in attempts
        for r in a.get("readings", [])
        if r.get("value") is not None and r.get("confidence", 0) >= 85
    ]
    values = {r["value"] for r in support} | set(prior_values)
    if len(values) != 1 or {r.get("inverted") for r in support} != {False, True}:
        return None
    if len({tuple(r["roi"]) for r in support}) < 2:
        return None
    x, _, width, _ = original_roi
    if not any(r["roi"][0] <= x and r["roi"][0] + r["roi"][2] >= x + width for r in support):
        return None
    return {
        "value": next(iter(values)),
        "support": support,
        "method": "cross_roi_currency_polarity_agreement",
    }


def recover_bet_polarities(frame, bet):
    """Retry visible currency labels; keep borders out without deleting digit strokes."""
    if bet.get("value") is not None or not bet.get("roi"):
        return bet
    prior = [bet, bet.get("alternative", {}), bet.get("grayscale_evidence", {})]
    if any(re.search(r"[+−-]\s*\d", r.get("text", "")) for r in prior):
        return bet
    if not any(re.search(r"[pр₽][.\s]*$", r.get("text", "")) for r in prior):
        return bet
    x, y, w, h = bet["roi"]
    if min(x, y) < 0 or w <= 0 or h <= 0 or x + w > frame.shape[1] or y + h > frame.shape[0]:
        return bet
    boxes = [[x, y, w, h], [x, max(0, y - 3), w, min(frame.shape[0], y + h + 3) - max(0, y - 3)]]
    crop = frame[y : y + h, x : x + w]
    mask = cv2.inRange(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV), (0, 0, 175), (179, 95, 255))
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    components = [c for c in stats[1:] if c[4] >= 3]
    # Do not remove a large connected stroke or a possible decimal/sign between glyphs.
    if len(components) >= 2 and all(c[2] < w * 0.5 and c[3] < h * 0.95 for c in components):
        left = max(0, x + min(c[0] for c in components) - 2)
        top = max(0, y + min(c[1] for c in components) - 2)
        right = min(frame.shape[1], x + max(c[0] + c[2] for c in components) + 2)
        bottom = min(frame.shape[0], y + max(c[1] + c[3] for c in components) + 2)
        boxes.append([int(left), int(top), int(right - left), int(bottom - top)])
    attempts = []
    reliable = [
        r["value"] for r in prior if r.get("confidence", 0) >= 85 and r.get("value") is not None
    ]
    reliable.extend(
        money(word["text"])
        for word in bet.get("words", [])
        if word.get("confidence", 0) >= 85
        and re.fullmatch(r"\d+(?:[.,]\d{1,2})?(?:\s*[pр₽]\.?)?", word["text"])
    )
    for bx, by, bw, bh in boxes:
        view = frame[by : by + bh, bx : bx + bw]
        reading = {**polarity_currency_amount(view.shape, view.tobytes()), "roi": [bx, by, bw, bh]}
        attempts.append(reading)
        if any(re.search(r"[+−-]\s*\d", r["text"]) for r in reading["readings"]):
            break
        reliable.extend(r["value"] for r in reading["readings"] if r["value"] is not None)
        candidate = reading["value"]
        if candidate is not None:
            conflicts = [v for v in reliable if v != candidate]
            return {
                **bet,
                "value": None if conflicts else candidate,
                "polarity_evidence": {"attempts": attempts, "conflicting_values": conflicts},
            }
    else:
        # Upscaling can turn a small intact amount into punctuation. Retry the
        # complete original ROI; do not crop away possible leading digits.
        reading = {
            **polarity_currency_amount(crop.shape, crop.tobytes(), scale=1),
            "roi": [x, y, w, h],
        }
        attempts.append(reading)
        candidate = reading["value"]
        if candidate is not None:
            conflicts = [v for v in reliable if v != candidate]
            return {
                **bet,
                "value": None if conflicts else candidate,
                "polarity_evidence": {"attempts": attempts, "conflicting_values": conflicts},
            }
    consensus = cross_roi_currency_consensus(attempts, bet["roi"], reliable)
    return {
        **bet,
        "value": consensus["value"] if consensus else None,
        "polarity_evidence": {"attempts": attempts, "cross_roi_consensus": consensus},
    }


def locate_dealer(rois, candidates):
    if len(candidates) != 1 or len(rois) < 2:
        return None
    x, y, w, h = candidates[0]["roi"]
    if len(rois) == 7:
        # PokerDom places the lower dealer buttons above the avatars, far from
        # the name plaques. Compare button anchors, not distances to nicknames.
        offsets = DEALER_ANCHOR_OFFSETS
        distances = sorted(
            (math.dist((x + w / 2, y + h / 2), (a + c * (0.5 + dx), b + d * (0.5 + dy))), i)
            for i, ((a, b, c, d), (dx, dy)) in enumerate(zip(rois, offsets, strict=True))
        )
        first, second = distances[:2]
        if first[0] < rois[first[1]][2] * 0.45 and second[0] > first[0] * 1.3:
            return first[1]
        return None
    distances = sorted(
        (math.dist((x + w / 2, y + h / 2), (a + c / 2, b + d / 2)), i)
        for i, (a, b, c, d) in enumerate(rois)
    )
    first, second = distances[:2]
    plaque_width = rois[first[1]][2]
    if first[0] < plaque_width * 1.6 and second[0] > first[0] * 1.3:
        return first[1]
    return None


def lower_bet_position(frame, roi, seat_index, original):
    """Read the alternate inner-table label position of the two lower seats."""
    if seat_index not in (4, 5) or original.get("value") is not None:
        return original
    # Retry a missing label, not a conflicting currency reading at another spot.
    if any(
        re.search(r"[pр₽]\.?$", r.get("text", "").strip())
        for r in (original, original.get("alternative", {}))
    ):
        return original
    x, y, w, h = roi
    cx = x + w * (0.5 + (0.95 if seat_index == 4 else -0.95))
    cy = y + h * (0.5 - 2.2)
    box = (round(cx - w * 0.3), round(cy - h * 0.2), round(w * 0.6), round(h * 0.4))
    bx, by, bw, bh = box
    if bx < 0 or by < 0 or bx + bw > frame.shape[1] or by + bh > frame.shape[0]:
        return original
    crop = frame[by : by + bh, bx : bx + bw]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    if np.count_nonzero(cv2.inRange(hsv, (0, 0, 175), (179, 95, 255))) < 12:
        return original
    reading = {**grayscale_amount(crop.shape, crop.tobytes()), "roi": list(box)}
    reading = recover_bet_polarities(frame, reading)
    if reading["value"] is None and not re.search(r"[+−-]\s*\d", reading.get("text", "")):
        full = polarity_currency_amount(crop.shape, crop.tobytes())
        attempts = [{**full, "roi": list(box)}]
        candidate = full["value"]
        cut = round(bh * 0.3)
        white = cv2.inRange(hsv, (0, 0, 175), (179, 95, 255))
        # Chips can occupy the line above the amount. Only separate at a blank
        # horizontal gap; keep the full width so signs and decimals survive.
        if (
            candidate is None
            and cut >= 2
            and not np.any(white[cut - 1 : cut + 1])
            and np.count_nonzero(white[cut + 1 :]) >= 12
            and not any(re.search(r"[+−-]\s*\d", r["text"]) for r in full["readings"])
        ):
            lower = crop[cut:]
            retry = polarity_currency_amount(lower.shape, lower.tobytes())
            attempts.append({**retry, "roi": [bx, by + cut, bw, bh - cut]})
            candidate = retry["value"]
        reliable = [r["value"] for a in attempts for r in a["readings"] if r["value"] is not None]
        reliable.extend(
            r["value"]
            for a in reading.get("polarity_evidence", {}).get("attempts", [])
            for r in a["readings"]
            if r["value"] is not None
        )
        if reading.get("confidence", 0) >= 85 and re.fullmatch(
            r"\d+(?:[.,]\d{1,2})?\s*[pр₽]\.?", reading.get("text", "")
        ):
            reliable.append(money(reading["text"]))
        conflicts = [value for value in reliable if value != candidate]
        reading = {
            **reading,
            "value": candidate if not conflicts else None,
            "inner_currency_evidence": {"attempts": attempts, "conflicting_values": conflicts},
        }
    return {**original, "value": reading["value"], "position_evidence": reading}


def corroborated_bet(bet):
    """A fallback cannot override a confident numeric reading of the same region."""
    if bet.get("value") is None:
        return bet
    source = bet.get("position_evidence", bet)
    check = {"value": bet["value"]}
    value = corroborated_line_value(
        {
            "full_line_evidence": check,
            "words": source.get("words", []),
            "number_evidence": source.get("number_evidence", {}),
        }
    )
    return {**bet, "value": value, "consistency_evidence": check}


def read_bets(frame, rois, *, skip_clear=True):
    """Read only the seven numeric bet regions, independently of names/actions."""
    return [read_bet(frame, roi, i, skip_clear=skip_clear) for i, roi in enumerate(rois)]


def read_bet(frame, roi, i, *, skip_clear=True):
    """One physical seat, also used by the bounded fast-reader worker pool."""
    offsets = [(0, 1.75), (0, 1.75), (0.8, 1), (-0.8, 1), (0.8, -1.2), (-0.8, -1.2), (0, -3.15)]
    x, y, w, h = roi
    dx, dy = offsets[i]
    cx, cy = x + w / 2 + dx * w, y + h / 2 + dy * h
    region = (round(cx - w * 0.25), round(cy - h * 0.2), round(w * 0.5), round(h * 0.4))
    visibility = bet_visibility(frame, roi, i)
    if skip_clear and visibility["state"] == "clear_felt_candidate":
        return {
            "roi": list(region),
            "text": "",
            "words": [],
            "value": None,
            "visibility": visibility,
            "ocr_skipped": "visually_clear_supported_regions",
        }
    bet = read_roi(frame, region, True)
    text = bet["text"].strip()
    value = money(text)
    # Currency is required: chip artwork or an isolated digit is not a bet label.
    reliable = (
        value is not None
        and bool(re.search(r"[рp₽]\.?$", text))
        and all(word["confidence"] >= 85 for word in bet["words"])
    )
    if not reliable and value is not None and re.search(r"[рp₽]\.?$", text):
        digits = [
            word for word in bet["words"] if re.fullmatch(r"\d+(?:[.,]\d{1,2})?", word["text"])
        ]
        if len(digits) == 1:
            check = button_number(frame, bet["roi"], digits[0])
            bet["number_evidence"] = check
            reliable = check["confidence"] >= 85 and check["value"] == value
    bet["value"] = value if reliable else None
    if not reliable:
        bx, by, bw, bh = bet["roi"]
        crop = frame[max(0, by) : by + bh, max(0, bx) : bx + bw]
        if crop.size:
            alternative = english_amount(crop.shape, crop.tobytes())
            bet["alternative"] = alternative
            bet["value"] = alternative["value"]
    bet = lower_bet_position(frame, roi, i, recover_amount(frame, bet))
    bet = corroborated_bet(recover_bet_polarities(frame, bet))
    if bet.get("value") is None:
        bet["visibility"] = visibility
    return bet


def read_blind_label(frame, roi):
    """Recognize centered muted-yellow blind labels, never voluntary actions."""
    x, y, w, h = roi
    region = (x + 3, y + round(h * 0.2), w - 6, round(h * 0.55))
    nx, ny, nw, nh = region
    crop = frame[ny : ny + nh, nx : nx + nw]
    if not crop.size:
        return None
    mask = cv2.inRange(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV), (15, 25, 80), (40, 150, 230))
    ys, xs = np.where(mask > 0)
    if len(xs) < 20 or xs.max() - xs.min() > nw * 0.3:
        return None
    if abs((xs.max() + xs.min()) / 2 - nw / 2) > nw * 0.1:
        return None
    reading = read_roi(frame, region)
    kind = {"мб": "small_blind", "бб": "big_blind"}.get(reading["text"].strip().casefold())
    if kind and reading["words"] and min(w["confidence"] for w in reading["words"]) >= 85:
        return {"blind": kind, **reading}
    if reading["words"] and min(w["confidence"] for w in reading["words"]) >= 85:
        return None  # Do not replace a confident conflicting text.
    # Small pale-yellow MB glyphs can disappear in the original RGB OCR.
    # Keep the same colour/position gate and require a strong white-mask read.
    alternative = read_roi(frame, region, True)
    kind = {"мб": "small_blind", "бб": "big_blind"}.get(alternative["text"].strip().casefold())
    if kind and alternative["words"] and min(w["confidence"] for w in alternative["words"]) >= 90:
        return {"blind": kind, **alternative, "method": "white_mask", "original": reading}
    return None


def read_action_label(frame, roi):
    """Read a voluntary action label independently of numeric and nickname OCR."""
    x, y, w, h = roi
    action = None
    name_roi = (x + 3, y + round(h * 0.2), w - 6, round(h * 0.55))
    nx, ny, nw, nh = name_roi
    crop = frame[ny : ny + nh, nx : nx + nw]
    if crop.size:
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        colored = cv2.inRange(hsv, (0, 110, 130), (179, 255, 255))
        if np.count_nonzero(colored) > w * 0.6:
            reading = read_roi(frame, name_roi, "colored")
            labels = {
                "чек": "check",
                "колл": "call",
                "уравнивает": "call",
                "сбрасывает": "fold",
                "пас": "fold",
                "ставка": "bet",
                "ставит": "bet",
                "повышает": "raise",
                "ва-банк": "all_in",
            }
            text = reading["text"].casefold().strip()
            if (
                text in labels
                and reading["words"]
                and min(word["confidence"] for word in reading["words"]) >= 85
            ):
                action = {"action": labels[text], **reading}
        if action is None:
            reading = dim_caption(frame, name_roi)
            labels = {
                "чек": "check",
                "сбрасывает": "fold",
                "пас": "fold",
                "ставит": "bet",
                "ставка": "bet",
                "повышает": "raise",
                "колл": "call",
                "уравнивает": "call",
                "ва-банк": "all_in",
            }
            if reading and reading["text"].casefold().strip() in labels:
                action = {"action": labels[reading["text"].casefold().strip()], **reading}
    if action and action["action"] == "all_in":
        action["semantics"] = "visible_all_in_label_not_call_or_raise"
    return action


def dim_caption(frame, roi):
    """Corroborate fading colored captions with OCR of original pixels."""
    x, y, w, h = roi
    crop = frame[y : y + h, x : x + w]
    if crop.size == 0:
        return None
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    warm = cv2.inRange(hsv, (0, 80, 65), (40, 255, 255)) | cv2.inRange(
        hsv, (165, 80, 65), (179, 255, 255)
    )
    green = cv2.inRange(hsv, (41, 100, 100), (95, 255, 255))
    glyphs = [
        c
        for c in cv2.connectedComponentsWithStats(green)[2][1:]
        if c[4] >= 4 and h * 0.15 <= c[3] <= h * 0.75
    ]
    if cv2.countNonZero(warm) < w * 0.2 and not (
        len(glyphs) >= 3 and sum(c[4] for c in glyphs) >= w * 0.2
    ):
        return None
    reading = read_roi(frame, roi, "dim_colored")
    allowed = {
        "чек",
        "сбрасывает",
        "пас",
        "ставит",
        "ставка",
        "повышает",
        "колл",
        "уравнивает",
        "ва-банк",
        "выигрывает",
    }
    words = reading["words"]
    if (
        reading["text"].casefold().strip() not in allowed
        or len(words) != 1
        or words[0]["confidence"] < 85
    ):
        return None
    a, b, ww, hh = words[0]["roi"]
    # A word touching an edge may have been clipped by a changed layout.
    if a < 2 or b < 2 or a + ww > w - 2 or b + hh > h - 2:
        return None
    left, top = max(x, x + a - 3), max(y, y + b - 3)
    right, bottom = min(x + w, x + a + ww + 3), min(y + h, y + b + hh + 3)
    check = read_roi(frame, [left, top, right - left, bottom - top])
    if (
        check["text"].casefold().strip() != reading["text"].casefold().strip()
        or not check["words"]
        or min(word["confidence"] for word in check["words"]) < 85
    ):
        return None
    return {**reading, "method": "dim_color_original_agreement", "original_evidence": check}


def read_settlement_label(frame, roi):
    x, y, w, h = roi
    region = (x + 3, y + round(h * 0.2), w - 6, round(h * 0.55))
    nx, ny, nw, nh = region
    crop = frame[ny : ny + nh, nx : nx + nw]
    if not crop.size:
        return None
    mask = cv2.inRange(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV), (0, 110, 130), (179, 255, 255))
    if np.count_nonzero(mask) <= w * 0.6:
        reading = dim_caption(frame, region)
        return (
            {"phase": "pot_awarded", **reading}
            if reading and reading["text"].strip().casefold() == "выигрывает"
            else None
        )
    reading = read_roi(frame, region, "colored")
    if (
        reading["text"].strip().casefold() == "выигрывает"
        and reading["words"]
        and min(word["confidence"] for word in reading["words"]) >= 85
    ):
        return {"phase": "pot_awarded", **reading}
    reading = dim_caption(frame, region)
    if reading and reading["text"].strip().casefold() == "выигрывает":
        return {"phase": "pot_awarded", **reading}
    return None


def analyze_table(frame, regions, dealer):
    rois = layout_panels(frame)
    slots = []
    dealer_slot = locate_dealer(rois, dealer)
    for i, (roi, bet) in enumerate(zip(rois, read_bets(frame, rois), strict=True)):
        action = read_action_label(frame, roi)
        settlement = read_settlement_label(frame, roi)
        slots.append(
            {
                "seat_index": i,
                "roi": list(roi),
                "is_dealer": i == dealer_slot if dealer_slot is not None else None,
                "current_bet": None if settlement else bet["value"],
                "settlement_label": settlement,
                "payout_evidence": bet if settlement else None,
                "bet_evidence": bet,
                "action_label": action,
                "blind_label": read_blind_label(frame, roi),
                "card_back_evidence": card_back_pair(frame, roi),
            }
        )
    return {
        "pot": pot(frame, regions),
        "controls": controls(frame),
        "slots": slots,
        "dealer_slot": dealer_slot,
        "ocr_language": "rus",
        "ocr_available": (TESSDATA / "rus.traineddata").exists(),
    }
