from datetime import datetime
from unittest.mock import Mock

import numpy as np
import pytest

from poker.hud.advisor_state import build_advisor_draft
from poker.hud.live_evidence import LiveEvidence
from poker.hud.title_stakes import (
    TitleStakesConfirmation,
    confirmed_title_stakes,
    parse_title_stakes,
)
from poker.hud.windows import Desktop
from tests.hud.test_hand_reconstruction import row

TITLE = "Григора #3765 - 1 р./2 р., Взрывной банк 2-5 ББ ~ каждые 14 рук БЛ Холдем - Рука: 12345678"


def source(number):
    result = row(number, backs=True)
    result.update(
        window=TITLE,
        window_handle=123,
        evidence_epoch=1,
        hero_seat=6,
        window_title_capture={"before": TITLE, "after": TITLE},
    )
    return result


def update(tracker, item):
    return tracker.update(item, item["context"]["hand_id"])


def test_title_limits_are_not_bomb_multipliers_or_forced_amounts():
    parsed = parse_title_stakes(TITLE)
    assert parsed["small_blind"] == "1" and parsed["big_blind"] == "2"
    assert parsed["table_id"] == "3765" and parsed["title_hand_id"] == "12345678"
    assert parsed["bomb_pot_schedule_advertised"] is True
    assert parsed["current_hand_is_bomb_pot"] is None and parsed["ruleset_verified"] is False
    decimal = parse_title_stakes(TITLE.replace("1 р./2 р.", "0,50 р./1,00 р."))
    assert decimal["small_blind"] == "0.50" and decimal["big_blind"] == "1.00"
    plain = parse_title_stakes("Стол #7 - 5 р./10 р., БЛ Холдем - Рука: 12345678")
    assert not plain["bomb_pot_schedule_advertised"] and not plain["ruleset_verified"]


@pytest.mark.parametrize(
    "title",
    [
        None,
        "Лобби PokerDom",
        TITLE + " extra",
        TITLE.replace("Холдем", "Омаха"),
        TITLE.replace("1 р./2 р.", "0 р./2 р."),
        TITLE.replace("1 р./2 р.", "3 р./2 р."),
        TITLE.replace("1 р./2 р.", "-1 р./2 р."),
        TITLE.replace("1 р./2 р.", "1.001 р./2 р."),
        TITLE.replace("1 р./2 р.", "1 $/2 $"),
    ],
)
def test_unknown_or_ambiguous_title_is_not_money(title):
    assert parse_title_stakes(title) is None


def test_two_current_captures_match_screen_identity_and_preserve_source_copies():
    tracker = TitleStakesConfirmation()
    first, second = source(1), source(2)
    assert update(tracker, first)["status"] == "awaiting_second_capture"
    result = update(tracker, second)
    assert confirmed_title_stakes(result, second, second["context"]["hand_id"])["big_blind"] == "2"
    result["confirmation_frames"][0]["source"]["window_handle"] = 9
    assert confirmed_title_stakes(result, second, second["context"]["hand_id"]) is None
    assert update(tracker, source(3))["status"] == "confirmed"


@pytest.mark.parametrize(
    "damage",
    [
        "legacy",
        "racing_title",
        "hand_mismatch",
        "confidence",
        "duplicate",
        "time",
        "epoch",
        "geometry",
        "handle",
        "seat",
        "limits",
        "gap",
        "missing",
    ],
)
def test_bad_or_different_capture_never_confirms_previous_limits(damage):
    tracker = TitleStakesConfirmation()
    first, second = source(1), source(2)
    update(tracker, first)
    if damage == "legacy":
        del second["window_title_capture"]
    elif damage == "racing_title":
        second["window_title_capture"]["before"] += " altered"
    elif damage == "hand_mismatch":
        second["context"]["hand_id"]["value"] = "99999999"
    elif damage == "confidence":
        second["context"]["hand_id"]["confidence"] = 79
    elif damage == "duplicate":
        second["frame_id"] = first["frame_id"]
    elif damage == "time":
        second["captured_at"] = first["captured_at"]
    elif damage == "epoch":
        second["evidence_epoch"] += 1
    elif damage == "geometry":
        second["client_rect"] = [10, 0, 1200, 1000]
    elif damage == "handle":
        second["window_handle"] += 1
    elif damage == "seat":
        second["hero_seat"] = 3
    elif damage == "limits":
        title = TITLE.replace("1 р./2 р.", "2 р./4 р.")
        second["window_title_capture"] = dict(before=title, after=title)
    elif damage == "gap":
        second["captured_at"] = source(8)["captured_at"]
    else:
        second["window_title_capture"] = dict(before=None, after=None)
    evidence = update(tracker, second)
    assert evidence["status"] != "confirmed"
    assert confirmed_title_stakes(evidence, second, second["context"]["hand_id"]) is None
    assert update(tracker, source(3))["status"] != "confirmed"


def test_live_evidence_and_advisor_convert_rubles_once_keep_all_other_blocks():
    live = LiveEvidence()
    for number in (1, 2):
        item = source(number)
        facts = live.update(item["context"], item, now=datetime.fromisoformat(item["captured_at"]))
    assert facts["table_stakes"]["status"] == "confirmed"
    draft = dict(
        hand_id="12345678",
        blockers=["stacks_unverified"],
        request=dict(
            is_my_turn=True,
            street_name="preflop",
            hero_hole_cards=["Ah", "Kd"],
            board_cards=[],
            total_pot=3,
            players=[],
        ),
    )
    result = build_advisor_draft(draft, live.tracker, item, item["context"], facts)
    assert result["observation"]["big_blind"] == 200  # quantum 0.01 RUB
    assert result["observation"]["history_complete"] is False
    assert set(result["blockers"]) >= {"stacks_unverified", "bomb_pot_hand_unverified"}
    assert not result["model_called"] and not result["would_send"]
    later = source(3)
    stale = build_advisor_draft(draft, live.tracker, later, later["context"], facts)
    assert stale["observation"]["big_blind"] is None
    live.reset()
    later["evidence_epoch"] = live.epoch
    resumed = live.update(later["context"], later, now=datetime.fromisoformat(later["captured_at"]))
    assert resumed["table_stakes"]["status"] == "awaiting_second_capture"


def test_desktop_title_reads_the_native_buffer_and_handles_disappearing_window():
    desktop = Desktop.__new__(Desktop)
    desktop.api = Mock()
    desktop.api.GetWindowTextLengthW.return_value = len(TITLE)

    def native_read(handle, buffer, size):
        assert handle == 123 and size == len(TITLE) + 1
        buffer.value = TITLE
        return len(TITLE)

    desktop.api.GetWindowTextW.side_effect = native_read
    assert desktop.title(123) == TITLE
    desktop.api.GetWindowTextLengthW.return_value = 0
    assert desktop.title(123) is None


def test_scan_brackets_exact_capture_without_replacing_stable_window_label(tmp_path):
    from poker.hud.app import HudApp

    hud = HudApp.__new__(HudApp)
    hud.exclusion_ok = True
    hud.target = Mock(handle=123, title="selected earlier")
    hud.desktop = Mock()
    hud.desktop.title.side_effect = [TITLE, TITLE + " changed"]
    hud.desktop.work_area.return_value = [0, 0, 1400, 1100]
    hud.capture = Mock()
    hud.capture.grab.return_value = np.zeros((1000, 1200, 4), dtype=np.uint8)
    hud.log_path = tmp_path / "hud.log"
    hud.capture_notice, hud.recorder = Mock(), Mock()
    hud.capture_notice_key = None
    hud.recorder.frame.return_value = 42
    hud.hero_seat, hud.capture_epoch = 6, 1
    hud.future = hud.names_future = hud.fast_future = Mock()
    hud.paused = False
    hud.scan((0, 0, 1200, 1000))
    meta = hud.recorder.frame.call_args.args[1]
    assert meta["window"] == "selected earlier" and meta["window_handle"] == 123
    assert meta["window_title_capture"] == {"before": TITLE, "after": TITLE + " changed"}
    assert (
        update(TitleStakesConfirmation(), {**meta, "context": source(1)["context"]})["reason"]
        == "title_changed_during_capture"
    )
