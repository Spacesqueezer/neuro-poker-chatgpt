from copy import deepcopy
from pathlib import Path

import cv2
import pytest

from poker.hud.pipeline import analyze_frame
from poker.hud.raise_cap import confirmed_raise_cap, refresh_round_trip_cap
from poker.hud.recognition import configure_ocr
from tests.hud.test_raise_cap import refreshed_setup, setup


def test_actual_lower_left_hero_cards_and_odds():
    path = Path("artifacts/hud/sessions/session_20261017_081302_81202a/ocr_frames/00000058.png")
    if not path.exists():
        pytest.skip("Local diagnostic source unavailable")
    configure_ocr()
    frame = cv2.imread(str(path))
    hand = analyze_frame(frame, False, hero_seat=4).hand
    assert hand.hero == ("8h", "5d")
    assert hand.board == ()
    assert hand.valid and hand.my_turn and hand.odds is not None
    assert analyze_frame(frame, False).hand.hero == ()

    # Revealed cards at the old central place must not be adopted as our hand.
    with_opponent = frame.copy()
    with_opponent[736:858, 552:728] = frame[624:746, 102:278]
    assert analyze_frame(with_opponent, False, hero_seat=4).hand.hero == ("8h", "5d")
    with_opponent[624:746, 102:278] = 0
    assert analyze_frame(with_opponent, False, hero_seat=4).hand.hero == ()


@pytest.mark.parametrize(
    "factory,confirm", [(setup, confirmed_raise_cap), (refreshed_setup, refresh_round_trip_cap)]
)
def test_cap_uses_selected_hero_not_bottom_opponent(factory, confirm):
    current, previous, facts = factory()
    current["context"]["hero_seat"] = previous["context"]["hero_seat"] = 4
    for key in ("stack_confirmations", "bet_confirmations"):
        facts[key][4] = deepcopy(facts[key][6])
        facts[key][6]["value"] = 999
    cap = confirm(current, previous, facts)
    assert cap["value"] == 102
    assert cap["hero_stack"]["value"] == 100
    assert cap["hero_current_bet"]["value"] == 2
    previous["context"]["hero_seat"] = 6
    assert confirm(current, previous, facts) is None


def test_advisor_sidecar_carries_selected_hero():
    from poker.hud.advisor_state import build_advisor_draft
    from poker.hud.hand_reconstruction import HandReconstructor

    current, _, _ = setup()
    context = current["context"]
    context["hero_seat"] = 4
    draft = {
        "hand_id": "12345678",
        "request": {
            "is_my_turn": True,
            "street_name": "preflop",
            "hero_hole_cards": ["Ah", "Kd"],
            "board_cards": [],
            "players": [{"seat_index": 4}, {"seat_index": 6}],
        },
    }
    result = build_advisor_draft(draft, HandReconstructor(), current, context, {})
    assert result["observation"]["hero_seat"] == 4
    assert result["would_send"] is False


def test_hero_participation_and_position_change_reset():
    from datetime import datetime

    from poker.hud.live_evidence import LiveEvidence
    from tests.hud.test_hand_reconstruction import row

    live = LiveEvidence()
    for n in (1, 2, 3):
        sample = row(n)
        sample["evidence_epoch"] = live.epoch
        sample["context"].update(
            hero_seat=4,
            decision_hand={
                "hero": ["8h", "5d"],
                "board": [],
                "valid": True,
                "my_turn": True,
            },
        )
        facts = live.update(
            sample["context"], sample, now=datetime.fromisoformat(sample["captured_at"])
        )
    assert facts["participation_evidence"][4]["cards_dealt"] is True
    assert 6 not in facts["participation_evidence"]
    sample = row(4)
    sample["evidence_epoch"] = live.epoch
    sample["context"]["hero_seat"] = 6
    assert (
        live.update(sample["context"], sample, now=datetime.fromisoformat(sample["captured_at"]))
        is None
    )
    assert live.previous is None
