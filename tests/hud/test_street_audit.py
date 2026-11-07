import json

from tests.hud.test_hand_reconstruction import row
from tools.audit_hud_streets import audit


def test_audit_keeps_transition_sources_and_separates_retrospective_frames(tmp_path):
    events = []
    for n in range(1, 7):
        item = row(n, board=() if n < 4 else ("Ah", "2c", "3s"))
        item.update(at=item["captured_at"], evidence_epoch=1)
        events.append({**item, "kind": "frame"})
        events.append({**item, "kind": "cards", "hand": item["context"]["decision_hand"]})
        events.append({**item, "kind": "decision_dry_run"})
        events.append({**item, "kind": "names"})
    (tmp_path / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events), encoding="utf8"
    )
    result = audit(tmp_path)
    assert len(result) == 1  # A request and names on one frame are not independent samples.
    boundary = result[0]["boundary"]
    assert [s["frame_id"] for s in boundary["confirmation_frames"]] == [4, 5]
    assert boundary["previous_street_source"]["frame_id"] == 3
    assert [s["frame_id"] for s in result[0]["review_frames"]] == [3, 4, 5]
    assert all(s["image"] is None for s in result[0]["review_frames"])
    assert boundary["previous_street_final_verified"] is False
