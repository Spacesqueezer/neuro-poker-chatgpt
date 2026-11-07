import numpy as np

from poker.hud.bet_visibility import bet_visibility


def test_clear_felt_is_only_a_candidate_not_numeric_zero():
    image = np.full((800, 1000, 3), (40, 120, 20), np.uint8)
    result = bet_visibility(image, (400, 150, 200, 80), 0)
    assert result["state"] == "clear_felt_candidate"
    assert result["numeric_zero_confirmed"] is False
    assert "value" not in result


def test_alternate_lower_position_blocks_absence_when_label_is_visible():
    image = np.full((800, 1000, 3), (40, 120, 20), np.uint8)
    roi = (100, 600, 200, 80)
    result = bet_visibility(image, roi, 4)
    assert result["state"] == "clear_felt_candidate"
    x, y, w, h = result["regions"][1]["roi"]
    image[y + h // 2 : y + h // 2 + 3, x + w // 2 : x + w // 2 + 8] = 255
    assert bet_visibility(image, roi, 4)["state"] == "unknown"


def test_obscured_or_clipped_region_is_unknown():
    black = np.zeros((800, 1000, 3), np.uint8)
    assert bet_visibility(black, (400, 150, 200, 80), 0)["state"] == "unknown"
    assert bet_visibility(black, (0, 0, 200, 80), 6)["reason"] == "roi_outside_image"


def test_clear_regions_skip_ocr_but_leave_amount_unknown(monkeypatch):
    from poker.hud import table_signals

    def unexpected(*args, **kwargs):
        raise AssertionError("OCR must not run on clear felt")

    monkeypatch.setattr(table_signals, "read_roi", unexpected)
    image = np.full((800, 1000, 3), (40, 120, 20), np.uint8)
    result = table_signals.read_bets(image, [(400, 150, 200, 80)])
    assert result[0]["value"] is None
    assert result[0]["ocr_skipped"] == "visually_clear_supported_regions"
