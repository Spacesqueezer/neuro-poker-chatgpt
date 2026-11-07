import numpy as np
import pytest

from poker.hud import recognition
from poker.hud.state import TableState


@pytest.mark.parametrize("text", ["snaketmb68...", "snaketmb68…"])
def test_truncated_client_label_is_not_a_player_identity(monkeypatch, text):
    monkeypatch.setattr(recognition, "find_panels", lambda frame: [(10, 10, 200, 80)])
    monkeypatch.setattr(recognition, "layout_panels", lambda frame: [])
    monkeypatch.setattr(recognition, "read_name_crop", lambda crop: (text, 95, ((text, 95),)))
    monkeypatch.setattr(recognition, "ocr_line", lambda crop: ("100 p.", 95))
    observation = recognition.analyze(np.zeros((100, 220, 3), np.uint8))[0]
    assert observation.name == ""
    assert observation.raw_name == text
    assert observation.status == "truncated_name"
    state = TableState()
    state.update([observation], (220, 100))
    state.correct(1, "FullNickname")
    seat = state.update([observation], (220, 100))[0]
    assert seat.name == "FullNickname" and seat.manual and not seat.conflict
