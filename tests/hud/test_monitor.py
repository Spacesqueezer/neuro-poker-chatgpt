from types import SimpleNamespace
from unittest.mock import Mock

from poker.hud.app import HudApp


def test_action_observations_are_deduplicated_and_failed_queue_is_retried():
    app = HudApp.__new__(HudApp)
    app.action_labels = {}
    app.observed_actions = 0
    app.recorder = SimpleNamespace(event=Mock(side_effect=[False, True, True]))
    app.monitor_status = Mock()
    app.paused = False
    app.target = SimpleNamespace(handle=1)
    app.desktop = SimpleNamespace(own_foreground=lambda _: True)
    context = {
        "hand_id": {"value": "123"},
        "decision_hand": {"street": "Флоп"},
        "table_signals": {
            "dealer_slot": 4,
            "slots": [{"seat_index": 4, "action_label": {"action": "call", "text": "УРАВНИВАЕТ"}}],
        },
    }
    meta = {"frame_id": 12}
    app.update_monitor(context, meta)
    assert app.observed_actions == 0
    app.update_monitor(context, meta)
    app.update_monitor(context, {"frame_id": 13})
    assert app.observed_actions == 1 and app.recorder.event.call_count == 2
    assert app.recorder.event.call_args.args[1]["verified_for_statistics"] is False
    context["decision_hand"]["street"] = "Тёрн"
    app.paused = True
    app.update_monitor(context, {"frame_id": 14})
    assert app.observed_actions == 2
    assert "приостановлено" in app.monitor_status.set.call_args.args[0]
