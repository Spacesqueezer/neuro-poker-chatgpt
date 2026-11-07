import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tools.audit_hud_contributions import action_stack_results


@pytest.mark.parametrize(
    "relative",
    [
        "client_history_2880027230/replay/observations_after.jsonl",
        "dense_20261007_middle/observations.jsonl",
        "dense_hand_2879914331/observations.jsonl",
        "dense_20261007_extra_blind/observations.jsonl",
    ],
)
def test_recorded_stack_pair_is_available_only_after_its_last_capture(relative):
    path = Path("artifacts/advisor") / relative
    if not path.is_file():
        pytest.skip("Local recorded evidence unavailable")
    rows = [json.loads(s) for s in path.read_text(encoding="utf8").splitlines()]
    results = action_stack_results(rows)
    assert results
    for result in results:
        timing = result["confirmation_timing"]
        captured = datetime.fromisoformat(timing["last_evidence_captured_at"])
        action_at = datetime.fromisoformat(result["action"]["captured_at"])
        assert timing["capture_span_after_action_ms"] == (captured - action_at) // timedelta(
            milliseconds=1
        )
        assert timing["processing_latency_ms"] is None
        prefix = [r for r in rows if datetime.fromisoformat(r["captured_at"]) <= captured]
        at_capture = action_stack_results(prefix)
        assert result in at_capture
        before_capture = action_stack_results(prefix[:-1])
        assert result not in before_capture
        assert result["contributed_delta"] is None
        assert not result["verified_for_training"]
