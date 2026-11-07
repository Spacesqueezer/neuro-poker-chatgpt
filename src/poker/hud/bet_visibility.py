"""Visual absence candidates, deliberately separate from numeric zero bets."""

import cv2
import numpy as np


def bet_visibility(frame, roi, seat_index):
    x, y, w, h = roi
    offsets = [(0, 1.75), (0, 1.75), (0.8, 1), (-0.8, 1), (0.8, -1.2), (-0.8, -1.2), (0, -3.15)]
    if not 0 <= seat_index < 7 or w <= 0 or h <= 0:
        return {"state": "unknown", "reason": "invalid_layout", "regions": []}
    positions = [(*offsets[seat_index], 0.7)]
    if seat_index in (4, 5):
        positions.append((0.95 if seat_index == 4 else -0.95, -2.2, 0.8))
    regions = []
    for dx, dy, width in positions:
        cx, cy = x + w * (0.5 + dx), y + h * (0.5 + dy)
        left, top = round(cx - w * width / 2), round(cy - h * 0.4)
        right, bottom = round(cx + w * width / 2), round(cy + h * 0.4)
        box = [left, top, right - left, bottom - top]
        if left < 0 or top < 0 or right > frame.shape[1] or bottom > frame.shape[0]:
            return {
                "state": "unknown",
                "reason": "roi_outside_image",
                "regions": regions,
                "roi": box,
            }
        hsv = cv2.cvtColor(frame[top:bottom, left:right], cv2.COLOR_BGR2HSV)
        felt = cv2.inRange(hsv, (35, 85, 35), (95, 255, 255))
        neutral = cv2.inRange(hsv, (0, 0, 130), (179, 95, 255))
        fraction = float(np.mean(felt > 0))
        neutral_pixels = int(np.count_nonzero(neutral))
        regions.append(
            {
                "roi": box,
                "felt_fraction": round(fraction, 4),
                "neutral_pixels": neutral_pixels,
                "clear": fraction >= 0.98 and neutral_pixels <= 5,
            }
        )
    return {
        "state": "clear_felt_candidate" if all(r["clear"] for r in regions) else "unknown",
        "reason": "supported_regions_visually_clear"
        if all(r["clear"] for r in regions)
        else "label_or_occlusion_or_background",
        "regions": regions,
        "numeric_zero_confirmed": False,
    }
