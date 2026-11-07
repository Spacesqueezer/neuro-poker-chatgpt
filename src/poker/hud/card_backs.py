"""Positive evidence of PokerDom's overlapping red card backs, not absence evidence."""

import math

import cv2


def card_back_pair(frame, plaque):
    x, y, w, h = plaque
    left, top = round(x + 0.12 * w), max(0, round(y - 0.95 * h))
    right = min(frame.shape[1], round(x + 0.88 * w))
    roi = [left, top, right - left, y - top]
    result = {"present": None, "roi": roi, "rectangles": []}
    crop = frame[top:y, left:right]
    if not crop.size:
        return result
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0, 75, 55), (12, 255, 255))
    mask |= cv2.inRange(hsv, (165, 75, 55), (179, 255, 255))
    boxes = []
    for contour in cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
        a, b, cw, ch = cv2.boundingRect(contour)
        # At small window sizes the plaque hides 1–2 raster rows of the backs.
        # Keep the paired widths, alignment, gap and fill checks below.
        if (
            b > h * 0.1
            and math.floor(h * 0.45) - 2 <= ch < h * 0.8
            and cv2.contourArea(contour) > cw * ch * 0.75
        ):
            boxes.append((a, b, cw, ch))
    boxes.sort()
    for first, second in zip(boxes, boxes[1:], strict=False):
        a, b, cw, ch = first
        d, e, fw, fh = second
        if (
            0.1 * w < cw < 0.22 * w
            and 0.24 * w < fw < 0.36 * w
            and abs(b - e) < h * 0.07
            and abs(ch - fh) < h * 0.07
            and 0 < d - a - cw < w * 0.08
        ):
            result.update(
                present=True, rectangles=[[left + a, top + b, cw, ch], [left + d, top + e, fw, fh]]
            )
            break
    return result
