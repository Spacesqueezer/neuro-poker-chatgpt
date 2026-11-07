"""Positive evidence of PokerDom's empty-seat icon; missing OCR is not emptiness."""

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np


@lru_cache(maxsize=1)
def empty_template():
    data = json.loads(
        Path(__file__).with_name("empty_seat_template.json").read_text(encoding="utf8")
    )
    return np.frombuffer(bytes.fromhex(data["pixels_hex"]), np.uint8).reshape(data["shape"])


@lru_cache(maxsize=1)
def empty_templates():
    data = json.loads(
        Path(__file__).with_name("empty_seat_template.json").read_text(encoding="utf8")
    )
    return [empty_template()] + [
        np.frombuffer(bytes.fromhex(item["pixels_hex"]), np.uint8).reshape(item["shape"])
        for item in data.get("alternate_templates", [])
    ]


def read_empty_seat(frame, roi):
    primary = empty_seat_region(frame, roi)
    if primary.get("empty") is True:
        return primary
    # Lower seats place the empty-seat icon above the former name plaque.
    # Search the same narrow column, retaining template/contrast requirements.
    raised = empty_seat_region(frame, roi, vertical_offset=-0.85)
    if raised.get("empty") is True:
        return {**raised, "search_position": "above_plaque", "primary_evidence": primary}
    return primary


def empty_seat_region(frame, roi, *, vertical_offset=0):
    x, y, w, h = roi
    y += round(h * vertical_offset)
    left, top = round(x + w * 0.25), round(y - h * 0.2)
    right, bottom = round(x + w * 0.75), round(y + h * 1.2)
    if w <= 0 or h <= 0 or left < 0 or top < 0 or right > frame.shape[1] or bottom > frame.shape[0]:
        return {"empty": None, "reason": "roi_outside_image"}
    crop = cv2.cvtColor(frame[top:bottom, left:right], cv2.COLOR_BGR2GRAY)
    crop = cv2.resize(crop, None, fx=221 / w, fy=221 / w, interpolation=cv2.INTER_CUBIC)
    template = empty_template()
    if crop.shape[0] < template.shape[0] or crop.shape[1] < template.shape[1]:
        return {"empty": None, "reason": "roi_too_small"}
    matches = [
        (cv2.minMaxLoc(cv2.matchTemplate(crop, candidate, cv2.TM_CCOEFF_NORMED)), index)
        for index, candidate in enumerate(empty_templates())
    ]
    (_, score, _, point), variant = max(matches, key=lambda item: item[0][1])
    template = empty_templates()[variant]
    px, py = point
    match = crop[py : py + template.shape[0], px : px + template.shape[1]]
    contrast = float(match.std())
    return {
        "empty": True if score >= 0.93 and contrast >= 12 else None,
        "basis": "explicit_empty_seat_icon",
        "similarity": round(score, 4),
        "template_variant": variant,
        "contrast": round(contrast, 2),
        "roi": [left, top, right - left, bottom - top],
    }


class EmptySeatTracker:
    """Require two distinct current icon readings; never infer hand participation."""

    def __init__(self):
        self.previous = {}
        self.last = None
        self.boundary = None

    def update(self, row, readings, occupied=()):
        at = datetime.fromisoformat(row["captured_at"])
        if self.last and (at <= self.last[0] or row["frame_id"] == self.last[1]):
            return {}
        boundary = (row.get("window"), tuple(row.get("client_rect", [])))
        if boundary != self.boundary:
            self.previous = {}
        self.boundary = boundary
        self.last = at, row["frame_id"]
        current, result = {}, {}
        for seat, reading in readings.items():
            if reading.get("empty") is not True or seat in occupied:
                continue
            source = {
                "frame_id": row["frame_id"],
                "captured_at": row["captured_at"],
                "image": row.get("image"),
                "reading": reading,
            }
            old = self.previous.get(seat)
            if (
                old
                and old["reading"].get("roi") == reading.get("roi")
                and 0 < (at - datetime.fromisoformat(old["captured_at"])).total_seconds() <= 5
            ):
                result[seat] = {
                    "occupied": False,
                    "basis": "repeated_empty_seat_icon",
                    "confirmation_frames": [old, source],
                }
            current[seat] = source
        self.previous = current
        return result


@lru_cache(maxsize=1)
def sitting_out_template():
    data = json.loads(
        Path(__file__).with_name("sitting_out_template.json").read_text(encoding="utf8")
    )
    gray = (
        np.frombuffer(bytes.fromhex(data["pixels_hex"]), np.uint8)
        .reshape(data["shape"])
        .astype(np.float32)
    )
    return gray - cv2.GaussianBlur(gray, (0, 0), 3)


def read_dim_status(frame, roi):
    x, y, w, h = roi
    if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > frame.shape[1] or y + h > frame.shape[0]:
        return None
    plaque = cv2.resize(frame[y : y + h, x : x + w], (221, 87))
    gray = cv2.cvtColor(plaque, cv2.COLOR_BGR2GRAY).astype(np.float32)
    detail = gray - cv2.GaussianBlur(gray, (0, 0), 3)
    region = detail[40:82, 36:185]
    template = sitting_out_template()
    _, score, _, point = cv2.minMaxLoc(cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED))
    px, py = point
    contrast = float(region[py : py + 34, px : px + 141].std())
    if score < 0.96 or contrast < 3:
        return None
    return {
        "status": "sitting_out",
        "method": "visual_template",
        "similarity": round(score, 4),
        "detail_contrast": round(contrast, 2),
        "roi": list(roi),
    }


def clear_empty_identities(state, slots, confirmed):
    """Forget position-bound names in replay memory, never delete player records."""
    removed = []
    for slot in slots:
        if slot["seat_index"] not in confirmed:
            continue
        x, y, w, _ = slot["roi"]
        for key, seat in list(state.seats.items()):
            sx, sy = seat.observation.roi[:2]
            if (sx - x) ** 2 + (sy - y) ** 2 < (w * 0.4) ** 2:
                del state.seats[key]
                removed.append(key)
    return removed


def filter_empty_players(payload, confirmed, hand):
    """Exclude only current empty places without evidence of a player in this hand."""
    excluded, retained = {}, []
    participants = hand.get("participants", {}) if hand else {}
    for player in payload["players"]:
        seat = player["seat_index"]
        evidence = confirmed.get(seat)
        safe = (
            hand is not None
            and evidence is not None
            and evidence.get("occupied") is False
            and len(evidence.get("confirmation_frames", [])) == 2
            and str(seat) not in participants
            and player.get("is_active") is not True
            and player.get("is_dealer") is not True
            and player.get("stack") is None
            and player.get("current_bet") in (None, 0)
        )
        if safe:
            excluded[seat] = evidence
        else:
            retained.append(player)
    return {**payload, "players": retained}, excluded
