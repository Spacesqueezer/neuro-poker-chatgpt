from pathlib import Path

import cv2
import pytest

from poker.hud.context import dealer_candidates, dealer_glyph
from poker.hud.recognition import configure_ocr, layout_panels
from poker.hud.table_signals import analyze_table, locate_dealer

SESSION = (
    Path(__file__).resolve().parents[2] / "artifacts/hud/sessions/session_20260911_012959_8898f1"
)


def frame(number):
    path = SESSION / f"frames/{number:08}.jpg"
    if not path.exists():
        pytest.skip("Local diagnostic frame unavailable")
    configure_ocr()
    return cv2.imread(str(path))


@pytest.mark.parametrize("number,seat", [(1, 0), (12, 0), (86, 4), (1675, 6)])
def test_metallic_rim_and_distant_lower_button(number, seat):
    image = frame(number)
    candidates = dealer_candidates(image)
    assert len(candidates) == 1
    assert locate_dealer(layout_panels(image), candidates) == seat


@pytest.mark.parametrize("number", [212, 295, 413, 592, 598, 711, 976, 1470, 2531, 2580])
def test_bright_action_glow_keeps_seven_seat_layout(number):
    rois = layout_panels(frame(number))
    assert len(rois) == 7
    assert abs(rois[0][0] - 356) < 5
    assert abs(rois[6][0] - 601) < 5


def test_chip_does_not_become_dealer_and_central_marker_is_rejected():
    image = frame(1)
    chip = image[486:525, 254:296]
    assert not dealer_glyph(chip.shape, chip.tobytes())
    assert locate_dealer(layout_panels(image), [{"roi": [670, 550, 42, 41]}]) is None


def test_raise_animation_is_recorded_as_an_action():
    signals = analyze_table(frame(1), {}, [])
    assert signals["slots"][0]["action_label"]["action"] == "raise"
