"""Face-up card recognition from white card rectangles and printed glyphs."""

import json
import re
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
import pytesseract

from poker.hud.models import CardObservation


def ink(image):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    return np.where((hsv[:, :, 1] > 60) | (hsv[:, :, 2] < 150), 255, 0).astype("uint8")


def normalize_shape(mask):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(contour)
    if cv2.contourArea(contour) < 8:
        return None
    isolated = np.zeros_like(mask)
    cv2.drawContours(isolated, [contour], -1, 255, -1)
    return cv2.resize(isolated[y : y + h, x : x + w], (64, 64), interpolation=cv2.INTER_AREA)


@lru_cache(maxsize=1)
def suit_shapes():
    shapes = {}
    for suit in "shdc":
        mask = np.zeros((110, 110), dtype=np.uint8)
        if suit == "d":
            cv2.fillPoly(mask, [np.array([(55, 4), (103, 55), (55, 105), (6, 55)])], 255)
        elif suit == "h":
            cv2.circle(mask, (32, 32), 27, 255, -1)
            cv2.circle(mask, (77, 32), 27, 255, -1)
            cv2.fillPoly(mask, [np.array([(8, 45), (101, 45), (55, 104)])], 255)
        elif suit == "s":
            cv2.circle(mask, (32, 60), 25, 255, -1)
            cv2.circle(mask, (77, 60), 25, 255, -1)
            cv2.fillPoly(mask, [np.array([(55, 4), (10, 52), (100, 52)])], 255)
            cv2.fillPoly(mask, [np.array([(51, 67), (44, 104), (67, 104), (59, 67)])], 255)
        else:
            cv2.circle(mask, (55, 27), 23, 255, -1)
            cv2.circle(mask, (29, 62), 25, 255, -1)
            cv2.circle(mask, (80, 62), 25, 255, -1)
            cv2.fillPoly(mask, [np.array([(51, 67), (44, 104), (67, 104), (59, 67)])], 255)
        shapes[suit] = normalize_shape(mask)
    return shapes


def read_suit(card):
    h, w = card.shape[:2]
    region = card[round(h * 0.36) : round(h * 0.70), round(w * 0.035) : round(w * 0.35)]
    mask = ink(region)
    shape = normalize_shape(mask)
    if shape is None:
        return "", 0.0
    colored = region[mask > 0]
    red = bool(len(colored) and np.mean(colored[:, 2].astype(float) - colored[:, 1]) > 35)
    candidates = "hd" if red else "sc"
    scores = []
    for suit in candidates:
        a, b = shape > 100, suit_shapes()[suit] > 100
        score = float(np.count_nonzero(a & b) / max(1, np.count_nonzero(a | b)))
        scores.append((score, suit))
    scores.sort(reverse=True)
    best, suit = scores[0]
    margin = best - scores[1][0]
    if not red:
        # Spades widen continuously from a point; clubs have a narrow top lobe.
        top_width = float(np.mean((shape > 100)[12:22]))
        suit = "s" if top_width > 0.55 else "c"
        shape_score = next(score for score, name in scores if name == suit)
        certainty = min(95.0, 70 + abs(top_width - 0.55) * 120)
        return (
            (suit, round(certainty, 1))
            if shape_score >= 0.65 and abs(top_width - 0.55) >= 0.05
            else ("", round(certainty, 1))
        )
    return (
        (suit, round(best * 100, 1))
        if best >= 0.62 and margin >= 0.06
        else ("", round(best * 100, 1))
    )


def rank_candidate(region, psm):
    mask = 255 - ink(region)
    mask = cv2.resize(mask, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
    mask = cv2.copyMakeBorder(mask, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=255)
    data = pytesseract.image_to_data(
        mask,
        config=f"--psm {psm} -c tessedit_char_whitelist=23456789TJQKA10",
        output_type=pytesseract.Output.DICT,
        timeout=3,
    )
    candidates = [
        (t, float(c))
        for t, c in zip(data["text"], data["conf"], strict=True)
        if re.fullmatch(r"10|[2-9TJQKA]", t)
    ]
    if not candidates:
        return "", 0.0
    value, score = max(candidates, key=lambda item: item[1])
    return ("T" if value == "10" else value), score


def native_rank_agreement(card):
    """Recover weak OCR only when grayscale and binary native crops agree."""
    h, w = card.shape[:2]
    for bottom, psm, scale, polarities in (
        (0.39, 7, 3, False),
        (0.33, 13, 3, False),
        (0.33, 13, 4, True),
    ):
        region = card[2 : round(h * bottom), 2 : round(w * 0.44)]
        if not region.size:
            continue
        readings = []
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        for index, source in enumerate((gray, 255 - gray if polarities else 255 - ink(region))):
            source = cv2.resize(source, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            source = cv2.copyMakeBorder(
                source,
                15,
                15,
                15,
                15,
                cv2.BORDER_CONSTANT,
                value=0 if polarities and index else 255,
            )
            data = pytesseract.image_to_data(
                source, config=f"--psm {psm}", output_type=pytesseract.Output.DICT, timeout=3
            )
            words = [
                (t.strip(), float(c))
                for t, c in zip(data["text"], data["conf"], strict=True)
                if t.strip()
            ]
            if (
                len(words) != 1
                or not re.fullmatch(r"10|[2-9TJQKA]", words[0][0])
                or words[0][1] < (85 if polarities else 70)
            ):
                break
            value, confidence = words[0]
            readings.append(("T" if value == "10" else value, confidence))
        if (
            len(readings) == 2
            and readings[0][0] == readings[1][0]
            and max(item[1] for item in readings) >= 80
        ):
            return readings[0][0], sum(item[1] for item in readings) / 2
    return "", 0.0


def read_rank(card):
    original = card
    card = cv2.resize(card, (102, 146), interpolation=cv2.INTER_CUBIC)
    h, w = card.shape[:2]
    corner = card[2 : round(h * 0.40), 3 : round(w * 0.44)]
    value, score = rank_candidate(corner, 7)
    corner_readings = [(value, score)]
    if score < 80:
        alternative, confidence = rank_candidate(corner, 13)
        corner_readings.append((alternative, confidence))
        if confidence > score:
            value, score = alternative, confidence
    if score < 80:
        # Less whitespace around a narrow rank fixes the PokerDom 9; keep the
        # original wider crop for 10 and never lower the acceptance threshold.
        alternative, confidence = rank_candidate(card[2:55, 3:36], 13)
        if confidence >= 85 and (not value or score < 55 or alternative == value):
            value, score = alternative, confidence
    if score < 85:
        alternative, confidence = segmented_rank(original)
        agrees = bool(value) and alternative == value and score >= 55 and confidence >= 85
        if agrees or (confidence >= 90 and (score < 55 or not value or alternative == value)):
            value, score = alternative, confidence
    if (
        value
        and 25 <= score < 55
        and sum(rank == value and confidence >= 25 for rank, confidence in corner_readings) >= 2
    ):
        shape_rank, shape_score = match_rank_shape(original, minimum=0.85, margin=0.12)
        if shape_rank == value:
            score = shape_score
    # Cross-check the second printed rank even when corner OCR is confident.
    large = card[round(h * 0.42) : h - 1, round(w * 0.32) : w - 1]
    other, other_score = rank_candidate(large, 13)
    if other_score < 80 and score < 80:
        alternative, confidence = rank_candidate(card[60:143, 32:99], 13)
        if confidence > other_score:
            other, other_score = alternative, confidence
    # A chip-distorted rectangle can make the large glyph look like another
    # rank. Preserve a weak corner reading only when its unscaled shape is an
    # exceptionally close match; a strong conflicting large reading still wins
    # the conflict check below (and is rejected if the shape disagrees).
    if value and other and value != other and 50 <= score < 85 and 85 <= other_score < 90:
        shape_rank, shape_score = match_rank_shape(original)
        if shape_rank == value and shape_score >= 95:
            return value, shape_score
    if value and score >= 90 and large_rank_obscured(original):
        # Blue/green chips can cover the large printed glyph. Do not use its
        # damaged OCR to veto a strong corner; the shape conflict check remains.
        other, other_score = "", 0
    if other and other == value:
        score = max(score, other_score)
    elif other and other_score >= 85:
        if value and score >= 55:
            shape_rank, shape_score = match_rank_shape(original)
            if shape_rank == value and score >= 85 and shape_score >= 90:
                return value, max(score, shape_score)
            return "", min(score, other_score)
        value, score = other, other_score
    shape_rank, shape_score = match_rank_shape(original)
    if shape_rank:
        if value and value != shape_rank and score >= 85:
            return "", min(score, shape_score)
        if not value or score < 85 or value == shape_rank:
            value, score = shape_rank, max(score if value == shape_rank else 0, shape_score)
    if score < 55:
        native, confidence = native_rank_agreement(original)
        if native and (not value or score < 25 or native == value):
            value, score = native, confidence
    return (value, score) if score >= 55 else ("", score)


def large_rank_obscured(card):
    h, w = card.shape[:2]
    region = card[round(h * 0.70) :, round(w * 0.32) :]
    if not region.size:
        return False
    mask = cv2.inRange(cv2.cvtColor(region, cv2.COLOR_BGR2HSV), (35, 100, 80), (145, 255, 255))
    return np.count_nonzero(mask) > max(12, mask.size * 0.12)


def rank_shape(card):
    h, w = card.shape[:2]
    region = card[3 : round(h * 0.36), 3 : round(w * 0.44)]
    if not region.size:
        return None
    mask = ink(region)
    _, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    selected = [
        (i, (x, y, cw, ch))
        for i, (x, y, cw, ch, area) in enumerate(stats[1:], 1)
        if area > 15 and ch > region.shape[0] * 0.45 and cw < region.shape[1] * 0.85
    ]
    if not 1 <= len(selected) <= 2:
        return None
    boxes = [b for _, b in selected]
    x, y = min(b[0] for b in boxes), min(b[1] for b in boxes)
    right, bottom = max(b[0] + b[2] for b in boxes), max(b[1] + b[3] for b in boxes)
    isolated = np.isin(labels, [i for i, _ in selected]).astype("uint8") * 255
    glyph = isolated[y:bottom, x:right]
    scale = min(46 / glyph.shape[1], 62 / glyph.shape[0])
    glyph = cv2.resize(
        glyph, (max(1, round(glyph.shape[1] * scale)), max(1, round(glyph.shape[0] * scale)))
    )
    result = np.zeros((64, 48), np.uint8)
    ox, oy = (48 - glyph.shape[1]) // 2, (64 - glyph.shape[0]) // 2
    result[oy : oy + glyph.shape[0], ox : ox + glyph.shape[1]] = glyph
    return result > 127


@lru_cache(maxsize=1)
def rank_templates():
    path = Path(__file__).with_name("rank_templates.json")
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf8"))
    return {
        rank: np.unpackbits(np.frombuffer(bytes.fromhex(item["bits"]), np.uint8))
        .reshape(64, 48)
        .astype(bool)
        for rank, item in data["templates"].items()
    }


@lru_cache(maxsize=1)
def alternate_rank_templates():
    path = Path(__file__).with_name("rank_templates.json")
    if not path.exists():
        return []
    return [
        (
            item,
            np.unpackbits(np.frombuffer(bytes.fromhex(item["bits"]), np.uint8))
            .reshape(64, 48)
            .astype(bool),
        )
        for item in json.loads(path.read_text(encoding="utf8")).get("alternate_templates", [])
    ]


def match_rank_shape(card, minimum=0.88, margin=0.08):
    shape = rank_shape(card)
    if shape is None:
        return "", 0.0
    scores = sorted(
        (
            (np.count_nonzero(shape & target) / max(1, np.count_nonzero(shape | target)), rank)
            for rank, target in rank_templates().items()
        ),
        reverse=True,
    )
    if len(scores) < 2:
        return "", 0.0
    if scores[0][0] < minimum or scores[0][0] - scores[1][0] < margin:
        # Small raster glyphs differ from downscaled large-card templates.
        # Preserve existing confident matches; compare distinct ranks, not
        # different exemplars of the same rank, when checking the margin.
        by_rank = {rank: score for score, rank in scores}
        h, w = card.shape[:2]
        for item, target in alternate_rank_templates():
            if not (
                item["card_width_range"][0] <= w <= item["card_width_range"][1]
                and item["card_height_range"][0] <= h <= item["card_height_range"][1]
            ):
                continue
            score = np.count_nonzero(shape & target) / max(1, np.count_nonzero(shape | target))
            by_rank[item["rank"]] = max(by_rank.get(item["rank"], 0), score)
        scores = sorted(((score, rank) for rank, score in by_rank.items()), reverse=True)
        if scores[0][0] < minimum or scores[0][0] - scores[1][0] < margin:
            return "", 0.0
    return scores[0][1], round(float(min(98, scores[0][0] * 100)), 1)


def segmented_rank(card):
    """Keep the printed corner glyph proportions when chips distort the card box."""
    h, w = card.shape[:2]
    region = card[3 : round(h * 0.36), 3 : round(w * 0.44)]
    if not region.size:
        return "", 0.0
    _, _, stats, _ = cv2.connectedComponentsWithStats(ink(region))
    boxes = [
        (x, y, cw, ch)
        for x, y, cw, ch, area in stats[1:]
        if area > 15 and ch > region.shape[0] * 0.45 and cw < region.shape[1] * 0.85
    ]
    if not 1 <= len(boxes) <= 2:
        return "", 0.0
    left, top = min(b[0] for b in boxes), min(b[1] for b in boxes)
    right, bottom = max(b[0] + b[2] for b in boxes), max(b[1] + b[3] for b in boxes)
    return rank_candidate(region[top:bottom, left:right], 13)


@lru_cache(maxsize=128)
def read_card_pixels(shape, pixels):
    """Reuse only byte-identical crops; changed glyphs must go through OCR."""
    card = np.frombuffer(pixels, dtype=np.uint8).reshape(shape)
    return (*read_rank(card), *read_suit(card))


def is_red_card_back(card):
    """The PokerDom back has a red interior; face cards have a pale background."""
    h, w = card.shape[:2]
    inner = card[round(h * 0.15) : round(h * 0.85), round(w * 0.15) : round(w * 0.85)]
    if not inner.size:
        return False
    hsv = cv2.cvtColor(inner, cv2.COLOR_BGR2HSV)
    red = cv2.inRange(hsv, (0, 65, 50), (12, 255, 255)) | cv2.inRange(
        hsv, (165, 65, 50), (179, 255, 255)
    )
    return bool(np.count_nonzero(red) / red.size > 0.75)


def split_joined_hero(hsv, mask, rect):
    """Split two face rectangles joined below the glyphs by a client tooltip."""
    x, y, w, h = rect
    height, width = mask.shape
    if not (
        1.25 < w / max(h, 1) < 1.55
        and 0.36 < x / width < 0.55
        and 0.65 < y / height < 0.82
        and 0.065 < h / height < 0.17
    ):
        return []
    band = hsv[y + 5 : y + round(h * 0.22), x : x + w]
    dark = cv2.inRange(band, (0, 0, 0), (179, 255, 100))
    gaps = np.flatnonzero((dark > 0).mean(axis=0) > 0.8)
    gaps = [int(g) for g in gaps if abs(g - w / 2) < w * 0.04]
    if not gaps or not 2 <= len(gaps) <= h * 0.06:
        return []
    left, right = gaps[0], gaps[-1] + 1
    if right - left != len(gaps):
        return []
    parts = [(x, y, left, h), (x + right, y, w - right, h)]
    for px, py, pw, ph in parts:
        white = mask[py : py + ph, px : px + pw]
        # A bright avatar arc has neither two filled faces nor two white tops.
        if not (
            0.6 < pw / ph < 0.8
            and np.count_nonzero(white) / white.size > 0.6
            and (white[3:6] > 0).mean() > 0.85
        ):
            return []
    return parts


def find_cards(frame, hero_seat=6):
    if type(hero_seat) is not int or not 0 <= hero_seat <= 6:
        raise ValueError("Invalid hero seat")
    from poker.hud.recognition import layout_panels

    seats = layout_panels(frame) if hero_seat != 6 else []
    hero_roi = seats[hero_seat] if len(seats) == 7 else None
    height, width = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0, 0, 175), (179, 70, 255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cards = []
    rectangles = [cv2.boundingRect(c) for c in contours]
    candidates = []
    for contour, rect in zip(contours, rectangles, strict=True):
        parts = split_joined_hero(hsv, mask, rect)
        # Keep the original single-card repair when the neighbour already has
        # its own contour; manufacturing it again would duplicate a card.
        if parts and any(
            abs(nx - parts[1][0]) <= rect[3] * 0.05
            and abs(ny - rect[1]) <= rect[3] * 0.04
            and 0.85 < nh / rect[3] < 1.15
            and 0.45 < nw / max(nh, 1) < 0.85
            for nx, ny, nw, nh in rectangles
        ):
            parts = []
        candidates.extend((contour, part, True) for part in parts)
        if not parts:
            candidates.append((contour, rect, False))
    for contour, (x, y, w, h), split_pair in candidates:
        # A hand-description tooltip can join the first hero card to white
        # pixels below its neighbour. The dark gap between their top edges
        # still identifies the first card's right boundary.
        joined_hero = (
            0.85 < w / max(h, 1) < 1.6
            and 0.36 < x / width < 0.55
            and 0.65 < y / height < 0.82
            and 0.065 < h / height < 0.17
            and any(
                0.6 < (nx - x) / h < 0.85
                and abs(ny - y) <= h * 0.04
                and 0.85 < nh / h < 1.15
                and 0.45 < nw / max(nh, 1) < 0.85
                for nx, ny, nw, nh in rectangles
            )
        )
        if joined_hero:
            band = hsv[y + 5 : y + max(6, round(h * 0.22)), x : x + w]
            separator = cv2.inRange(band, (0, 0, 0), (179, 255, 100))
            gaps = np.flatnonzero((separator > 0).mean(axis=0) > 0.8)
            candidates = [int(g) for g in gaps if 0.6 < g / h < 0.8]
            if candidates:
                right = candidates[0]
                if right + 1 in candidates:
                    w = right
        area = (
            np.count_nonzero(mask[y : y + h, x : x + w])
            if joined_hero or split_pair
            else cv2.contourArea(contour)
        )
        if not (
            0.45 < w / max(h, 1) < 0.85
            and 0.025 < w / width < 0.085
            and 0.065 < h / height < 0.17
            and area > 0.60 * w * h
        ):
            continue
        cx, cy = (x + w / 2) / width, (y + h / 2) / height
        zone = (
            "board"
            if 0.28 < cx < 0.74 and 0.30 < cy < 0.66
            else "hero"
            if (
                (hero_seat == 6 and 0.36 < cx < 0.64 and 0.65 < cy < 0.86)
                or (
                    hero_roi is not None
                    and hero_roi[0] - hero_roi[2] * 0.1
                    < x + w / 2
                    < hero_roi[0] + hero_roi[2] * 1.1
                    and hero_roi[1] - hero_roi[3] * 2.2 < y + h / 2 < hero_roi[1]
                )
            )
            else ""
        )
        if not zone:
            continue
        # Chips can join a sliver of the preceding card to this contour.
        # A vertical felt gap near its left edge separates the actual rectangle.
        band = hsv[y + 5 : y + max(6, round(h * 0.22)), x : x + w]
        felt = cv2.inRange(band, (30, 70, 20), (100, 255, 255))
        gap = np.flatnonzero((felt > 0).mean(axis=0)[: max(1, round(w * 0.15))] > 0.8)
        if len(gap) >= 2:
            left = int(gap[-1]) + 2
            white = mask[y + 5 : y + max(6, round(h * 0.22)), x : x + w]
            rights = [
                np.flatnonzero(row)[-1] + 1 for row in white if np.count_nonzero(row) > w * 0.35
            ]
            if rights:
                right = int(np.median(rights))
                corrected_width = right - left
                if corrected_width > w * 0.8:
                    x, w = x + left, corrected_width
                    h = min(h, round(w / 0.694))
        crop = frame[y : y + h, x : x + w]
        if is_red_card_back(crop):
            continue
        rank, rank_score, suit, suit_score = read_card_pixels(crop.shape, crop.tobytes())
        value = rank + suit if rank and suit else ""
        if not value and zone == "board":
            repaired = board_face_bounds(mask, (x, y, w, h), rectangles)
            if repaired:
                rx, ry, rw, rh = repaired
                face = frame[ry : ry + rh, rx : rx + rw]
                rr, rs, ss, sc = read_card_pixels(face.shape, face.tobytes())
                if rr and ss and min(rs, sc) >= 75:
                    x, y, w, h = repaired
                    value, rank_score, suit_score = rr + ss, rs, sc
        cards.append(
            CardObservation(
                zone, (x, y, w, h), value, min(rank_score, suit_score), rank_score, suit_score
            )
        )
    cards.extend(unread_board_faces(mask, rectangles, cards))
    hero = [c for c in cards if c.zone == "hero"]
    if hero_seat == 6 and (len(hero) != 2 or any(not c.value or c.confidence < 75 for c in hero)):
        repaired = recover_hero_tops(frame, mask, rectangles)
        if repaired and all(
            not old.value
            or any(
                abs(old.roi[0] - new.roi[0]) < new.roi[2] * 0.15 and old.value == new.value
                for new in repaired
            )
            for old in hero
        ):
            cards = [c for c in cards if c.zone != "hero"] + repaired
    return sorted(cards, key=lambda c: (c.zone, c.roi[0]))


def unread_board_faces(mask, rectangles, cards):
    """A missing face must not leave a falsely complete earlier street.

    This geometry guard supplies an unknown card, never guesses its rank or suit.
    Require an established, evenly spaced board. Interior gaps are explicit;
    the next position additionally needs an aligned tall white face. Short chip
    stacks and unrelated white UI are excluded.
    """
    board = sorted((c for c in cards if c.zone == "board"), key=lambda c: c.roi[0])
    if len(board) not in (3, 4):
        return []
    rects = np.array([c.roi for c in board], dtype=float)
    pw, ph = np.median(rects[:, 2:4], axis=0)
    top = float(np.median(rects[:, 1]))
    steps = np.diff(rects[:, 0])
    adjacent = steps[(steps > pw) & (steps < 1.2 * pw)]
    if not len(adjacent):
        return []
    step = float(np.median(adjacent))
    positions = np.rint((rects[:, 0] - rects[0, 0]) / step).astype(int)
    if (
        not 0.65 < pw / max(ph, 1) < 0.75
        or not 1.0 < step / pw < 1.2
        or np.any(abs(rects[:, 0] - rects[0, 0] - positions * step) > pw * 0.08)
        or len(set(positions)) != len(positions)
        or positions[-1] > 4
        or np.any(abs(rects[:, 1] - top) > ph * 0.04)
        or np.any(abs(rects[:, 2] - pw) > pw * 0.08)
        or np.any(abs(rects[:, 3] - ph) > ph * 0.08)
    ):
        return []
    missing = sorted(set(range(int(positions[-1]) + 1)) - set(positions))
    if missing:
        # Aligned cards on both sides establish an occupied interior position.
        # Chips may hide its entire white contour. Keep the gap explicit instead
        # of interpreting four survivors of a river as a complete turn.
        return [
            CardObservation(
                "board", (round(rects[0, 0] + n * step), round(top), round(pw), round(ph)), "", 0.0
            )
            for n in missing
        ]
    expected_center = rects[-1, 0] + step + pw / 2
    matches = []
    for x, y, w, h in rectangles:
        if (
            abs(x + w / 2 - expected_center) <= pw * 0.18
            and abs(y - top) <= ph * 0.04
            and 0.12 * pw <= w <= 1.08 * pw
            and 0.85 * ph <= h <= 1.08 * ph
            and x > rects[-1, 0] + pw
        ):
            face = mask[y : y + h, x : x + w]
            if face.size and np.mean(face > 0) >= 0.40:
                matches.append((x, y, w, h))
    if len(matches) != 1:
        return []
    return [CardObservation("board", matches[0], "", 0.0)]


def board_face_bounds(mask, rect, rectangles):
    """Bound a chip-joined board face using two aligned peers and its white top."""
    x, y, w, h = rect
    height, width = mask.shape
    peers = [
        (nx, ny, nw, nh)
        for nx, ny, nw, nh in rectangles
        if abs(ny - y) <= 3
        and nx != x
        and 0.28 < (nx + nw / 2) / width < 0.74
        and 0.30 < (ny + nh / 2) / height < 0.66
        and 0.65 < nw / max(nh, 1) < 0.75
        and 0.065 < nh / height < 0.17
    ]
    if len(peers) < 2:
        return None
    pw, ph = (float(np.median([p[i] for p in peers])) for i in (2, 3))
    if any(abs(p[2] - pw) > pw * 0.05 or abs(p[3] - ph) > ph * 0.05 for p in peers):
        return None
    if not ph * 1.08 < h < ph * 1.4 or not pw * 0.95 < w < pw * 1.3:
        return None
    top = (mask[y + 2 : y + 4, x : x + w] > 0).all(axis=0)
    changes = np.diff(np.r_[False, top, False].astype(int))
    runs = [
        (int(a), int(b))
        for a, b in zip(np.flatnonzero(changes == 1), np.flatnonzero(changes == -1), strict=True)
    ]
    runs = [(a, b) for a, b in runs if abs((b - a + 4) - pw) <= pw * 0.05]
    if len(runs) != 1:
        return None
    left, right = runs[0]
    left, right = max(0, left - 2), min(w, right + 2)
    rh = round(ph)
    face = mask[y : y + rh, x + left : x + right]
    if (face > 0).mean() < 0.60:
        return None
    return x + left, y, right - left, rh


def recover_hero_tops(frame, mask, rectangles):
    """Recover tooltip-cut faces only from a pair of aligned white top edges."""
    height, width = mask.shape
    tops = sorted(
        {
            y
            for x, y, w, h in rectangles
            if 0.36 < x / width < 0.55
            and 0.65 < y / height < 0.82
            and h / height > 0.065
            and w / width > 0.025
        }
    )
    for y in tops:
        band = (mask[y + 2 : y + 4] > 0).mean(axis=0) > 0.8
        changes = np.diff(np.r_[False, band, False].astype(int))
        edges = [
            (int(left) - 2, int(right - left) + 4)
            for left, right in zip(
                np.flatnonzero(changes == 1), np.flatnonzero(changes == -1), strict=True
            )
            if 0.36 < left / width < 0.60 and 0.04 < (right - left) / width < 0.08
        ]
        if len(edges) != 2:
            continue
        (lx, lw), (rx, rw) = edges
        if abs(lw - rw) > lw * 0.05 or not 0.02 < (rx - lx - lw) / lw < 0.16:
            continue
        found = []
        for x, w in edges:
            h = round(w / 0.694)
            if x < 0 or x + w > width or y + h > height:
                break
            face = mask[y + 5 : y + round(h * 0.68), x : x + w]
            if not face.size or (face > 0).mean() < 0.65:
                break
            crop = frame[y : y + h, x : x + w]
            if is_red_card_back(crop):
                break
            rank, rs, suit, ss = read_card_pixels(crop.shape, crop.tobytes())
            if not rank or not suit or min(rs, ss) < 75:
                break
            found.append(CardObservation("hero", (x, y, w, h), rank + suit, min(rs, ss), rs, ss))
        if len(found) == 2 and found[0].value != found[1].value:
            return found
    return []
