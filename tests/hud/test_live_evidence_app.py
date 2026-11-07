from concurrent.futures import Future
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import numpy as np
import pytest

from poker.hud.app import HudApp
from poker.hud.bet_bridge import BetBridge
from poker.hud.decision_stream import DecisionStream
from poker.hud.hand import HandObservation
from poker.hud.live_evidence import LiveEvidence
from poker.hud.state import TableState
from tests.hud.test_confirmed_bets import row


def app(tmp_path):
    hud = HudApp.__new__(HudApp)
    source = row(3)
    context = source.pop("context")
    source["captured_at"] = datetime.now(UTC).isoformat()
    hud.live_evidence = LiveEvidence()
    hud.fast_evidence = LiveEvidence()
    hud.capture_epoch = hud.live_evidence.epoch
    hud.cards_meta = {}
    hud.bet_bridge = BetBridge()
    source["evidence_epoch"] = hud.live_evidence.epoch
    hud.hand = HandObservation(hero=("Ah", "Kd"), valid=True, my_turn=True)
    context["decision_hand"] = hud.hand.to_dict()
    context.update(
        regions={"table_text": {"raw_text": "", "words": []}}, errors=[], dealer_candidates=[]
    )
    hud.names_future = Future()
    hud.names_future.set_result(([], context))
    hud.names_context = source, 1, (1200, 1000), np.zeros((1000, 1200, 3), np.uint8)
    hud.generation, hud.paused = 1, False
    hud.target, hud.desktop = Mock(), Mock()
    hud.desktop.rect.return_value = (0, 0, 1200, 1000)
    hud.desktop.own_foreground.return_value = True
    hud.state = TableState()
    hud.decision_stream = DecisionStream()
    hud.recorder = Mock(path=tmp_path, limit_reached=False, dropped=0, error=None)
    hud.update_monitor = Mock()
    hud.monitor_status = Mock()
    hud.monitor_status.get.return_value = "Нейросеть выключена"
    hud.stats_collector, hud.stats_status, hud.log = Mock(), Mock(), Mock()
    return hud


def test_names_worker_updates_ui_statistics_without_emitting_decisions(tmp_path):
    hud = app(tmp_path)
    facts = {
        "participation_evidence": {0: {"cards_dealt": True, "is_active": True}},
        "bet_confirmations": {0: {"value": 2}},
        "stack_confirmations": {0: {"value": 100}},
    }
    hud.live_evidence.update = Mock(return_value=facts)
    hud.collect_names()
    calls = {c.args[0]: c.args[1] for c in hud.recorder.event.call_args_list}
    assert "live_evidence" in calls
    assert calls["live_evidence"]["stack_confirmations"][0]["value"] == 100
    assert "decision_dry_run" not in calls
    hud.stats_collector.observe.assert_called_once()


@pytest.mark.parametrize("lossless", [False, True])
def test_live_sources_prefer_saved_lossless_frame(tmp_path, lossless):
    hud = app(tmp_path)
    frame_id = hud.names_context[0]["frame_id"]
    jpeg = tmp_path / "frames" / f"{frame_id:08d}.jpg"
    jpeg.parent.mkdir()
    jpeg.write_bytes(b"saved jpeg")
    expected = jpeg
    if lossless:
        expected = tmp_path / "ocr_frames" / f"{frame_id:08d}.png"
        expected.parent.mkdir()
        expected.write_bytes(b"saved png")
    facts = {"participation_evidence": {}, "bet_confirmations": {}, "stack_confirmations": {}}
    hud.live_evidence.update = Mock(return_value=facts)
    hud.bet_bridge.augment = Mock(return_value=facts)
    hud.collect_names()
    assert hud.live_evidence.update.call_args.args[1]["image"] == str(expected.resolve())
    assert hud.bet_bridge.augment.call_args.args[0]["image"] == str(expected.resolve())


def test_late_result_is_logged_but_never_becomes_request(tmp_path):
    hud = app(tmp_path)
    hud.names_context[0]["captured_at"] = (datetime.now(UTC) - timedelta(seconds=6)).isoformat()
    hud.decision_stream.count = 2
    fast_state = hud.fast_evidence.tracker
    hud.collect_names()
    kinds = [c.args[0] for c in hud.recorder.event.call_args_list]
    assert "live_evidence_rejected" in kinds
    assert "names" in kinds
    assert "decision_dry_run" not in kinds
    assert hud.decision_stream.count == 2
    assert hud.capture_epoch == 1
    assert hud.fast_evidence.tracker is fast_state
    hud.stats_collector.observe.assert_not_called()


def test_explicit_capture_boundary_clears_both_streams(tmp_path):
    hud = app(tmp_path)
    hud.decision_stream.count = 2
    hud.cards_meta = {"frame_id": 3}
    old_tracker = hud.fast_evidence.tracker
    hud.reset_capture_evidence()
    assert hud.capture_epoch == 2
    assert hud.live_evidence.epoch == hud.fast_evidence.epoch == hud.capture_epoch
    assert hud.fast_evidence.tracker is not old_tracker
    assert hud.decision_stream.count == 0
    assert hud.cards_meta == {}
    hud.collect_names()
    hud.stats_collector.observe.assert_not_called()


def test_moved_table_rejects_old_capture_even_when_size_is_unchanged(tmp_path):
    hud = app(tmp_path)
    hud.desktop.rect.return_value = (20, 0, 1200, 1000)
    hud.live_evidence.update = Mock()
    hud.collect_names()
    hud.live_evidence.update.assert_not_called()
    hud.stats_collector.observe.assert_not_called()
