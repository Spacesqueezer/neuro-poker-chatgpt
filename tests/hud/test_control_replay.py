from tools.replay_hud_controls import select_frames


def row(kind, number):
    return {"kind": kind, "frame_id": number, "captured_at": f"2026-09-12T05:00:{number:02d}+00:00"}


def test_dense_replay_preserves_frames_between_name_jobs():
    names = {
        **row("names", 2),
        "context": {"table_signals": {"controls": {"flags": {"can_call": True}}}},
    }
    events = [row("frame", 3), names, row("frame", 2), row("cards", 1), row("frame", 1)]
    assert select_frames(events) == [names]
    dense = select_frames(events, all_frames=True)
    assert [r["frame_id"] for r in dense] == [1, 2, 3]
    assert dense[1] is names
    assert "context" not in dense[0]
    assert "context" not in dense[2]


def test_replay_range_includes_endpoints_and_keeps_capture_time():
    events = [row("frame", n) for n in range(1, 5)]
    assert select_frames(events, True, 2, 3) == events[1:3]
