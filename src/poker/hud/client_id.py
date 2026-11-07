"""Read the PokerDom hand number from the vertical client label."""

import re
from functools import lru_cache

import cv2
import numpy as np
import pytesseract


@lru_cache(maxsize=32)
def _read(shape, pixels):
    crop = np.frombuffer(pixels, np.uint8).reshape(shape)
    horizontal = cv2.rotate(crop, cv2.ROTATE_90_COUNTERCLOCKWISE)
    horizontal = cv2.resize(horizontal, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    data = pytesseract.image_to_data(
        horizontal,
        config="--psm 7 -c tessedit_char_whitelist=#0123456789",
        output_type=pytesseract.Output.DICT,
        timeout=4,
    )
    for text, confidence in zip(data["text"], data["conf"], strict=True):
        match = re.fullmatch(r"#(\d{8,14})", text.strip())
        if match:
            return {"value": match[1], "raw_text": text, "confidence": float(confidence)}
    return {"value": "", "raw_text": " ".join(data["text"]).strip(), "confidence": 0.0}


@lru_cache(maxsize=32)
def _read_padded(shape, pixels, scales=(2, 4)):
    crop = np.frombuffer(pixels, np.uint8).reshape(shape)
    horizontal = cv2.rotate(crop, cv2.ROTATE_90_COUNTERCLOCKWISE)
    gray = 255 - cv2.cvtColor(horizontal, cv2.COLOR_BGR2GRAY)
    readings = []
    for scale in scales:
        image = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
        image = cv2.copyMakeBorder(image, 20, 20, 20, 20, cv2.BORDER_REPLICATE)
        data = pytesseract.image_to_data(
            image, config="--psm 7", output_type=pytesseract.Output.DICT, timeout=4
        )
        words = [
            (t.strip(), float(c))
            for t, c in zip(data["text"], data["conf"], strict=True)
            if t.strip()
        ]
        if len(words) != 1 or not re.fullmatch(r"#\d{8,14}", words[0][0]) or words[0][1] < 80:
            if len(scales) == 2 or any(confidence >= 80 for _, confidence in words):
                return None
            continue
        readings.append({"text": words[0][0], "confidence": words[0][1], "scale": scale})
    if len(readings) < 2 or len({r["text"] for r in readings}) != 1:
        return None
    return {
        "value": readings[0]["text"][1:],
        "raw_text": readings[0]["text"],
        "confidence": min(r["confidence"] for r in readings),
        "method": "padded_grayscale_agreement",
        "readings": readings,
    }


def read_hand_id(frame):
    h, w = frame.shape[:2]
    x, y, bottom = w - round(w * 0.024), round(h * 0.025), round(h * 0.30)
    crop = frame[y:bottom, x:w]
    result = {**_read(crop.shape, crop.tobytes()), "roi": [x, y, w - x, bottom - y]}
    if result["confidence"] < 80:
        # Exclude the green window outline and excess vertical whitespace.
        top, end, right = round(h * 0.04), round(h * 0.20), w - 3
        tight = frame[top:end, x:right]
        alternative = _read(tight.shape, tight.tobytes())
        if alternative["confidence"] > result["confidence"]:
            result = {**alternative, "roi": [x, top, right - x, end - top]}
        if result["confidence"] < 80:
            padded = _read_padded(tight.shape, tight.tobytes())
            if padded is not None:
                result = {**padded, "roi": [x, top, right - x, end - top]}
            else:
                # The resized window's gray outer border survives the first
                # crop and is replicated into the OCR padding. Stay further
                # inside the frame, then require two independent scale reads.
                inner_right = w - max(6, round(w * 0.005))
                inner = frame[top:end, x:inner_right]
                if inner.size:
                    padded = _read_padded(inner.shape, inner.tobytes(), (2, 4, 3))
                    if padded is None:
                        padded = _read_padded(inner.shape, inner.tobytes(), (2, 4, 3, 1))
                    if padded is not None:
                        result = {
                            **padded,
                            "method": "inner_grayscale_agreement",
                            "roi": [x, top, inner_right - x, end - top],
                        }
    return result
