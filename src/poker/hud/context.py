"""Slow diagnostic OCR for table text and dealer candidates, never inferred bets."""

import math
import time
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from functools import lru_cache

import cv2
import numpy as np
import pytesseract

from poker.hud.cards import find_cards
from poker.hud.client_id import read_hand_id
from poker.hud.hand import observe
from poker.hud.pipeline import my_turn
from poker.hud.recognition import analyze, layout_panels
from poker.hud.seat_evidence import read_stack
from poker.hud.seat_occupancy import read_empty_seat
from poker.hud.slider import field_and_knob
from poker.hud.table_signals import DEALER_ANCHOR_OFFSETS, analyze_table


@lru_cache(maxsize=32)
def text_region(shape, pixels, psm=11):
    crop = np.frombuffer(pixels, np.uint8).reshape(shape)
    if psm == 10:
        crop = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    return pytesseract.image_to_string(crop, config=f"--psm {psm}", timeout=4).strip()


@lru_cache(maxsize=128)
def dealer_glyph(shape, pixels):
    """Read the centre, excluding the metallic rim which OCR mistakes for letters."""
    crop = np.frombuffer(pixels, np.uint8).reshape(shape)
    h, w = crop.shape[:2]
    inner = crop[round(h * 0.2) : round(h * 0.8), round(w * 0.2) : round(w * 0.8)]
    gray = cv2.cvtColor(inner, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask = cv2.copyMakeBorder(mask, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
    data = pytesseract.image_to_data(
        mask, config="--psm 10", output_type=pytesseract.Output.DICT, timeout=3
    )
    words = [
        (t.strip(), float(c)) for t, c in zip(data["text"], data["conf"], strict=True) if t.strip()
    ]
    return len(words) == 1 and words[0][0] == "D" and words[0][1] >= 85


def dealer_candidates(frame):
    h, w = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0, 0, 100), (179, 100, 255))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for contour in contours:
        x, y, cw, ch = cv2.boundingRect(contour)
        if not (
            0.015 < cw / w < 0.045
            and 0.8 < cw / ch < 1.2
            and 0.1 < x / w < 0.9
            and 0.2 < y / h < 0.8
        ):
            continue
        if cv2.contourArea(contour) / (cw * ch) < 0.6:
            continue
        crop = frame[y : y + ch, x : x + cw]
        text = text_region(crop.shape, crop.tobytes(), 10)
        full_read = text.strip(" .|\n") in ("D", "d")
        if full_read or dealer_glyph(crop.shape, crop.tobytes()):
            candidates.append(
                {
                    "roi": [x, y, cw, ch],
                    "raw_text": text,
                    "method": "full" if full_read else "inner_glyph",
                }
            )
        if len(candidates) >= 3:
            break
    return (
        candidates
        or anchored_dealer_candidates(frame)
        or anchored_dealer_candidates(frame, circle_threshold=18)
    )


def anchored_dealer_candidates(frame, *, circle_threshold=22):
    """Recover a circular D marker whose rim touches another bright object."""
    panels = layout_panels(frame)
    if len(panels) != 7:
        return []
    candidates = []
    for (x, y, w, h), (dx, dy) in zip(panels, DEALER_ANCHOR_OFFSETS, strict=True):
        cx, cy = x + w * (0.5 + dx), y + h * (0.5 + dy)
        left, top = round(cx - w * 0.25), round(cy - w * 0.25)
        right, bottom = round(cx + w * 0.25), round(cy + w * 0.25)
        if left < 0 or top < 0 or right > frame.shape[1] or bottom > frame.shape[0]:
            continue
        gray = cv2.cvtColor(frame[top:bottom, left:right], cv2.COLOR_BGR2GRAY)
        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            1,
            w * 0.15,
            param1=100,
            param2=circle_threshold,
            minRadius=round(w * 0.08),
            maxRadius=round(w * 0.14),
        )
        if circles is None:
            continue
        for a, b, radius in circles[0]:
            a, b, radius = round(a), round(b), round(radius)
            bx, by, size = left + a - radius, top + b - radius, 2 * radius + 1
            if bx < left or by < top or bx + size > right or by + size > bottom:
                continue
            crop = frame[by : by + size, bx : bx + size]
            if not dealer_glyph(crop.shape, crop.tobytes()):
                continue
            if any(math.dist((bx, by), c["roi"][:2]) < radius for c in candidates):
                continue
            candidates.append(
                {
                    "roi": [bx, by, size, size],
                    "raw_text": "D",
                    "method": "anchor_circle_inner_glyph",
                    "circle_threshold": circle_threshold,
                }
            )
    return candidates


@lru_cache(maxsize=32)
def region_words(shape, pixels):
    image = np.frombuffer(pixels, np.uint8).reshape(shape)
    data = pytesseract.image_to_data(
        image, config="--psm 11", output_type=pytesseract.Output.DICT, timeout=4
    )
    return [
        {
            "text": text,
            "confidence": float(data["conf"][i]),
            "roi": [data[k][i] for k in ("left", "top", "width", "height")],
        }
        for i, text in enumerate(data["text"])
        if text.strip()
    ]


def stack_hidden_by_action(slot):
    """Only a confident caption inside this plaque can suppress its stack OCR."""
    label = slot.get("action_label") or {}
    words = label.get("words", [])
    if (
        label.get("action") not in {"fold", "check", "call", "bet", "raise", "all_in"}
        or not words
        or any(word.get("confidence", 0) < 85 for word in words)
        or slot.get("settlement_label")
    ):
        return False
    roi, plaque = label.get("roi", []), slot.get("roi", [])
    if len(roi) != 4 or len(plaque) != 4:
        return False
    x, y, w, h = roi
    px, py, pw, ph = plaque
    return w > 0 and h > 0 and px <= x and py <= y and x + w <= px + pw and y + h <= py + ph


def read_table_stacks(frame, slots):
    """Bound OCR concurrency; preserve seat order and isolate per-seat failures."""
    readings, errors = {}, []
    if not slots:
        return readings, errors
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="hud-stack") as pool:
        pending = [(slot, pool.submit(read_slot_stack, frame, slot)) for slot in slots]
        for slot, future in pending:
            seat = slot["seat_index"]
            try:
                readings[seat] = future.result()
            except Exception as error:
                readings[seat] = {"value": None, "error": str(error)}
                errors.append(f"stack_{seat}: {error}")
    return readings, errors


def read_slot_stack(frame, slot):
    """Shared checked reader for the name and independent decision workers."""
    if stack_hidden_by_action(slot):
        return {
            "value": None,
            "rejection": "stack_hidden_by_action_caption",
            "plaque_roi": list(slot["roi"]),
            "action_evidence": deepcopy(slot["action_label"]),
        }
    return read_stack(frame, slot["roi"], read_status=False)


def analyze_names(frame, hero_seat=6):
    started = time.monotonic()
    players = analyze(frame)
    names_ms = (time.monotonic() - started) * 1000
    h, w = frame.shape[:2]
    regions = {}
    errors = []
    try:
        hand_id = read_hand_id(frame)
        cards = find_cards(frame) if hero_seat == 6 else find_cards(frame, hero_seat=hero_seat)
        hero_visible = len([c for c in cards if c.zone == "hero"]) == 2
        decision_hand = observe(cards, my_turn(frame))
    except Exception as error:
        errors.append(f"hand_id: {error}")
        hand_id, hero_visible = {}, False
        decision_hand = observe([])
    for name, bounds in {
        "table_text": (0.2, 0.3, 0.8, 0.7),
        "controls": (0.25, 0.88, 0.8, 1),
    }.items():
        x1, y1, x2, y2 = bounds
        x, y, right, bottom = round(w * x1), round(h * y1), round(w * x2), round(h * y2)
        crop = frame[y:bottom, x:right]
        try:
            words = region_words(crop.shape, crop.tobytes())
        except Exception as error:
            errors.append(f"{name}: {error}")
            words = []
        regions[name] = {
            "roi": [x, y, right - x, bottom - y],
            "raw_text": " ".join(word["text"] for word in words),
            "words": words,
            "word_coordinates": "relative_to_region",
        }
    try:
        dealer = dealer_candidates(frame)
    except Exception as error:
        errors.append(f"dealer: {error}")
        dealer = []
    try:
        table_signals = analyze_table(frame, regions, dealer)
        for slot in table_signals.get("slots", []):
            if slot.get("action_label"):
                for player in players:
                    if math.dist(player.roi[:2], slot["roi"][:2]) < slot["roi"][2] * 0.4:
                        player.name = ""
                        player.status = "action:" + slot["action_label"]["action"]
    except Exception as error:
        errors.append(f"table_signals: {error}")
        table_signals = {}
    if decision_hand.my_turn:
        try:
            table_signals["slider_evidence"] = field_and_knob(frame)
        except Exception as error:
            errors.append(f"slider: {error}")
    stacks_started = time.monotonic()
    stack_readings, stack_errors = read_table_stacks(frame, table_signals.get("slots", []))
    errors.extend(stack_errors)
    stacks_ms = round((time.monotonic() - stacks_started) * 1000, 1)
    empty_started = time.monotonic()
    empty_readings = {}
    for slot in table_signals.get("slots", []):
        try:
            empty_readings[slot["seat_index"]] = read_empty_seat(frame, slot["roi"])
        except Exception as error:
            empty_readings[slot["seat_index"]] = {"empty": None, "error": str(error)}
            errors.append(f"empty_seat_{slot['seat_index']}: {error}")
    return players, {
        "regions": regions,
        "hand_id": hand_id,
        "hero_seat": hero_seat,
        "hero_visible": hero_visible,
        "decision_hand": decision_hand.to_dict(),
        "dealer_candidates": dealer,
        "table_signals": table_signals,
        "stack_readings": stack_readings,
        "empty_seat_readings": empty_readings,
        "empty_seats_ms": round((time.monotonic() - empty_started) * 1000, 1),
        "stacks_ms": stacks_ms,
        "errors": errors,
        "names_ms": round(names_ms, 1),
        "total_ms": round((time.monotonic() - started) * 1000, 1),
    }
