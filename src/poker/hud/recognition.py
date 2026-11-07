"""Frame-local panel detection and OCR, independent of the desktop UI."""

import re
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
import pytesseract

from poker.hud.models import PlayerObservation


def configure_ocr():
    executable = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if executable.exists():
        pytesseract.pytesseract.tesseract_cmd = str(executable)
    return str(pytesseract.get_tesseract_version())


def find_panels(frame):
    """Locate the dark name plaques, including an obscured action plaque.

    Multiple thresholds and normalized dimensions support scaled PokerDom tables.
    No coordinates or recognized labels from the old capture metadata are used.
    """
    height, width = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    found = []
    for value in (32, 40, 46):
        mask = cv2.inRange(hsv, (0, 0, 0), (179, 100, value))
        contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if not (2.1 < w / max(h, 1) < 3.9 and 0.065 < w / width < 0.15):
                continue
            if not (0.12 < y / height < 0.89 and 0 <= x / width < 0.95):
                continue
            if h < height * 0.025 or cv2.contourArea(contour) < w * h * 0.65:
                continue
            roi = (x, y, w, min(round(w / 2.55), height - y))
            if any(abs(x - a) < w * 0.25 and abs(y - b) < h * 0.5 for a, b, _, _ in found):
                continue
            found.append(roi)
    return sorted(found, key=lambda box: (box[1], box[0]))[:9]


def ocr_line(image):
    return cached_line(image.shape, image.tobytes())


@lru_cache(maxsize=128)
def cached_line(shape, pixels):
    image = np.frombuffer(pixels, dtype=np.uint8).reshape(shape)
    scaled = cv2.resize(image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    data = pytesseract.image_to_data(
        scaled, config="--psm 7", output_type=pytesseract.Output.DICT, timeout=4
    )
    words = [
        (text.strip(), float(conf))
        for text, conf in zip(data["text"], data["conf"], strict=True)
        if text.strip() and float(conf) >= 0
    ]
    if not words:
        return "", 0.0
    return " ".join(text for text, _ in words), sum(conf for _, conf in words) / len(words)


@lru_cache(maxsize=128)
def native_name_line(shape, pixels):
    """Small name glyphs can lose their shape when enlarged; retry at native resolution."""
    crop = np.frombuffer(pixels, dtype=np.uint8).reshape(shape)
    gray = 255 - cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    data = pytesseract.image_to_data(
        gray,
        config="--psm 7 -c load_system_dawg=0 -c load_freq_dawg=0",
        output_type=pytesseract.Output.DICT,
        timeout=4,
    )
    words = [
        (t.strip(), float(c)) for t, c in zip(data["text"], data["conf"], strict=True) if t.strip()
    ]
    return " ".join(t for t, _ in words), min((c for _, c in words), default=0)


@lru_cache(maxsize=128)
def horizontal_background_name(shape, pixels):
    """Remove a long horizontal table rim behind a translucent name plaque."""
    crop = np.frombuffer(pixels, np.uint8).reshape(shape)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    saturation = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)[:, :, 1]
    first = max(3, round(shape[0] * 0.4) | 1)
    checks = []
    for width in (first, first + 2):
        detail = cv2.morphologyEx(
            gray, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_RECT, (width, 1))
        )
        detail = cv2.normalize(detail, None, 0, 255, cv2.NORM_MINMAX)
        foreground = detail > 127
        if np.count_nonzero(foreground) < 20 or np.mean(saturation[foreground] <= 65) < 0.85:
            return ()  # A colored action label must not become a player identity.
        checks.append(ocr_line(255 - detail))
    return tuple(checks)


@lru_cache(maxsize=128)
def diagonal_background_name(shape, pixels):
    """Retry only a slanted background rim entering through the plaque boundary."""
    crop = np.frombuffer(pixels, np.uint8).reshape(shape)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    lines = cv2.HoughLinesP(
        cv2.Canny(gray, 15, 40),
        1,
        np.pi / 180,
        12,
        minLineLength=shape[1] * 0.2,
        maxLineGap=5,
    )
    slopes = []
    for x1, y1, x2, y2 in () if lines is None else lines.reshape(-1, 4):
        if x2 == x1:
            continue
        slope = (y2 - y1) / (x2 - x1)
        if x1 <= 3 and y2 <= 3 and 0.2 <= -slope <= 0.5:
            slopes.append(float(slope))
    if not slopes:
        return ()
    slope = float(np.median(slopes))
    checks = []
    saturation = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)[:, :, 1]
    for ratio in (0.6, 0.8):
        width = max(3, round(shape[0] * ratio) | 1)
        height = max(3, round(width * -slope) | 1)
        kernel = np.zeros((height, width), np.uint8)
        cv2.line(kernel, (0, height - 1), (width - 1, 0), 1, 1)
        detail = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)
        detail = cv2.normalize(detail, None, 0, 255, cv2.NORM_MINMAX)
        foreground = detail > 127
        if np.count_nonzero(foreground) < 20 or np.mean(saturation[foreground] <= 65) < 0.85:
            return ()
        checks.append(ocr_line(255 - detail))
    return tuple(checks)


@lru_cache(maxsize=128)
def rim_name_crosscheck(shape, pixels):
    """Cross-check even confident names when a long rim crosses the text band."""
    crop = np.frombuffer(pixels, np.uint8).reshape(shape)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    lines = cv2.HoughLinesP(
        cv2.Canny(gray, 15, 40),
        1,
        np.pi / 180,
        20,
        minLineLength=shape[1] * 0.65,
        maxLineGap=10,
    )
    if not any(
        abs(x2 - x1) >= shape[1] * 0.65
        and abs(y2 - y1) <= abs(x2 - x1) * 0.05
        and shape[0] * 0.2 < (y1 + y2) / 2 < shape[0] * 0.85
        for x1, y1, x2, y2 in (() if lines is None else lines.reshape(-1, 4))
    ):
        return ()
    saturation = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)[:, :, 1]
    first = max(3, round(shape[0] * 0.2) | 1)
    checks = []
    for width in (first, first + 2):
        detail = cv2.morphologyEx(
            gray, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_RECT, (width, 1))
        )
        detail = cv2.normalize(detail, None, 0, 255, cv2.NORM_MINMAX)
        foreground = detail > 127
        if np.count_nonzero(foreground) < 20 or np.mean(saturation[foreground] <= 65) < 0.85:
            return ()
        checks.append(ocr_line(255 - detail))
    return tuple(checks)


def read_name_crop(name_crop):
    # Player names are bright neutral text. Action labels are colored/dim.
    hsv = cv2.cvtColor(name_crop, cv2.COLOR_BGR2HSV)
    bright = cv2.inRange(hsv, (0, 0, 80), (179, 65, 255))
    text, confidence = (
        ocr_line(name_crop)
        if np.count_nonzero(bright) > (name_crop.shape[1] + 6) * 0.2
        else ("", 0.0)
    )
    alternatives = [(text, confidence)]
    if confidence < 65 and np.count_nonzero(bright) > (name_crop.shape[1] + 6) * 0.2:
        gray = cv2.cvtColor(name_crop, cv2.COLOR_BGR2GRAY)
        enhanced = cv2.morphologyEx(
            gray, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        )
        alternative, score = ocr_line(enhanced)
        alternatives.append((alternative, score))
        if score > confidence:
            text, confidence = alternative, score
    if confidence < 65 and np.count_nonzero(bright) > (name_crop.shape[1] + 6) * 0.2:
        alternative, score = native_name_line(name_crop.shape, name_crop.tobytes())
        agrees = any(alternative == candidate and prior >= 25 for candidate, prior in alternatives)
        alternatives.append((alternative, score))
        if score >= 65 and agrees:
            text, confidence = alternative, score
    if confidence < 65 and np.count_nonzero(bright) > (name_crop.shape[1] + 6) * 0.2:
        checks = horizontal_background_name(name_crop.shape, name_crop.tobytes())
        if len(checks) == 2 and checks[0][0] == checks[1][0] and min(s for _, s in checks) >= 85:
            candidate = checks[0][0]
            if all(score < 65 or prior == candidate for prior, score in alternatives):
                text, confidence = candidate, min(score for _, score in checks)
        alternatives.extend(checks)
    if confidence < 65 and np.count_nonzero(bright) > (name_crop.shape[1] + 6) * 0.2:
        checks = diagonal_background_name(name_crop.shape, name_crop.tobytes())
        if len(checks) == 2 and checks[0][0] == checks[1][0] and min(s for _, s in checks) >= 85:
            candidate = checks[0][0]
            if (
                re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.\-]{1,30}", candidate)
                and not candidate.endswith("...")
                and any(candidate in prior.split() and score >= 25 for prior, score in alternatives)
                and all(score < 65 or prior == candidate for prior, score in alternatives)
            ):
                text, confidence = candidate, min(score for _, score in checks)
        alternatives.extend(checks)
    if confidence >= 65 and re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.\-]{1,30}", text):
        checks = rim_name_crosscheck(name_crop.shape, name_crop.tobytes())
        alternatives.extend(checks)
        if (
            len(checks) == 2
            and checks[0][0] == checks[1][0]
            and checks[0][0] != text
            and min(score for _, score in checks) >= 85
            and re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.\-]{1,30}", checks[0][0])
        ):
            # Do not invent a correction or create an alias from conflicting OCR.
            return text, 0.0, tuple(alternatives)
    return text, confidence, tuple(alternatives)


def analyze(frame):
    detected = find_panels(frame)
    candidates = layout_panels(frame) or detected
    if not candidates:
        return []
    # Each worker reads the same immutable frame; map preserves physical seat order.
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="hud-name") as pool:
        return [
            player
            for player in pool.map(lambda roi: analyze_panel(frame, roi, detected), candidates)
            if player is not None
        ]


def analyze_panel(frame, roi, detected):
    x, y, w, h = roi
    # Actual plaque boundaries override drifting felt-based estimates.
    nearby = [roi for roi in detected if abs(roi[0] - x) < w * 0.6 and abs(roi[1] - y) < h * 0.5]
    if nearby:
        x, y, w, h = min(nearby, key=lambda r: abs(r[0] - x) + abs(r[1] - y))
    plaque = frame[y : y + h, x : x + w]
    name_crop = plaque[2 : max(3, round(h * 0.54)), 3:-3]
    text, confidence, alternatives = read_name_crop(name_crop)
    conflicted = confidence == 0 and any(
        candidate == text and score >= 65 for candidate, score in alternatives
    )
    truncated = text.endswith(("...", "…"))
    valid = (
        bool(re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.\-]{1,30}", text))
        and confidence >= 45
        and not truncated
    )
    stack, _ = ocr_line(plaque[round(h * 0.54) :, 3:-3])
    stack = stack.strip()
    if not re.fullmatch(r"\d[\d ]*(?:[.,]\d{1,2})?\s*(?:[pр₽]\.?)?", stack):
        stack = ""
    visible_plaque = any(abs(x - a) < w * 0.3 and abs(y - b) < h * 0.4 for a, b, _, _ in detected)
    plaque_hsv = cv2.cvtColor(plaque, cv2.COLOR_BGR2HSV)
    visible_plaque |= (
        float(plaque_hsv[:, :, 1].mean()) < 35 and float(np.mean(plaque_hsv[:, :, 2] < 65)) > 0.7
    )
    if not visible_plaque and not valid and not stack and not conflicted:
        return None
    if not valid and not stack and sum(c.isalpha() for c in text) < 3:
        return None
    return PlayerObservation(
        (x, y, w, h),
        text if valid else "",
        round(confidence, 1),
        stack,
        "conflicting_name_readings"
        if conflicted
        else "recognized"
        if valid
        else "truncated_name"
        if truncated
        else "hidden_or_uncertain",
        text,
        tuple(alternatives),
    )


def layout_panels(frame):
    """PokerDom seven-seat skin, anchored to felt, not desktop resolution.

    Used when translucent action animations remove the dark plaque boundary.
    OCR must still confirm text/stack before a fallback location becomes occupied.
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (35, 85, 35), (95, 255, 255))
    # A green action/avatar glow can join the felt and shift every seat ROI.
    # Remove narrow connections at a scale proportional to the client width.
    diameter = max(3, round(frame.shape[1] * 0.025) | 1)
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (diameter, diameter)),
    )
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return []
    contour = max(contours, key=cv2.contourArea)
    x, y, width, height = cv2.boundingRect(contour)
    if not (
        1.7 < width / max(1, height) < 2.7
        and cv2.contourArea(contour) > frame.shape[0] * frame.shape[1] * 0.15
    ):
        return []
    positions = [
        (0.201, -0.096),
        (0.636, -0.096),
        (-0.085, 0.276),
        (0.921, 0.276),
        (-0.016, 1.01),
        (0.853, 1.01),
        (0.418, 1.245),
    ]
    result = []
    for dx, dy in positions:
        px, py = round(x + dx * width), round(y + dy * height)
        pw, ph = round(width * 0.166), round(width * 0.065)
        if px >= 0 and py >= 0 and px + pw <= frame.shape[1] and py + ph <= frame.shape[0]:
            result.append((px, py, pw, ph))
        else:
            # Never renumber subsequent seats when the inferred layout is clipped.
            return []
    return result


def annotate(frame, players, cards=()):
    result = frame.copy()
    for player in players:
        x, y, w, h = player.roi
        cv2.rectangle(result, (x, y), (x + w, y + h), (100, 220, 80), 2)
        cv2.putText(
            result,
            f"{player.name or '?'} {player.confidence:.0f}",
            (x, max(18, y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (100, 220, 80),
            2,
        )
    for card in cards:
        item = card.to_dict() if hasattr(card, "to_dict") else card
        x, y, w, h = item["roi"]
        color = (255, 200, 80) if item["value"] else (70, 70, 255)
        cv2.rectangle(result, (x, y), (x + w, y + h), color, 2)
        cv2.putText(
            result,
            f"{item['zone']} {item['value'] or '?'}",
            (x, max(16, y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
        )
    return result
