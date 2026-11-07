import json
from pathlib import Path

import pytest

from poker.hud.contribution_reconciliation import reconcile_observations


def test_dense_recording_recovers_hero_call_without_inventing_postflop_totals():
    path = Path("artifacts/advisor/dense_hand_2879914331/observations.jsonl")
    if not path.is_file():
        pytest.skip("Local dense hand observations unavailable")
    rows = [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()]
    result = reconcile_observations(sorted(rows, key=lambda r: r["captured_at"]))
    assert len(rows) == 111
    assert {
        (i["seat"], i["stack_decrease"], i["street_bet_increase"]) for i in result["intervals"]
    } == {(2, 1000, 1000), (6, 700, 700)}
    for interval in result["intervals"]:
        assert interval["hand_id"] == "2879914331"
        assert interval["hand_contribution"] is None
        assert interval["history_complete"] is False
        assert interval["status"] == "balanced_observed_endpoints"
