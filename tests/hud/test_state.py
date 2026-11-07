from poker.hud.layout import overlap, place_card
from poker.hud.models import PlayerObservation
from poker.hud.state import TableState


def player(name="Alice", x=100):
    return PlayerObservation((x, 100, 200, 80), name, 90, "100", "recognized")


def test_name_needs_confirmation_and_survives_action_label():
    state = TableState()
    assert not state.update([player()], (1000, 600))[0].name
    assert state.update([player()], (1000, 600))[0].name == "Alice"
    assert state.update([player("")], (1000, 600))[0].name == "Alice"


def test_manual_name_does_not_follow_another_seat_and_conflict_is_explicit():
    state = TableState()
    state.update([player(), player("Bob", 500)], (1000, 600))
    state.correct(1, "Alicia")
    state.update([player("Bob", 500), player("Other")], (1000, 600))
    assert state.seats[1].name == "Alicia"
    assert state.seats[1].conflict
    assert state.seats[2].name == "Bob"


def test_departure_and_resize_clear_manual_identity():
    state = TableState()
    state.update([player()], (1000, 600))
    state.correct(1, "Manual")
    for _ in range(10):
        state.update([], (1000, 600))
    assert not state.seats
    assert not state.update([player()], (1000, 600))[0].manual
    state.correct(2, "Manual")
    assert not state.update([player()], (1200, 700))[0].manual


def test_manual_typo_correction_accepts_original_ocr_alias():
    state = TableState()
    state.update([player("A1ice")], (1000, 600))
    state.correct(1, "Alice")
    seat = state.update([player("A1ice")], (1000, 600))[0]
    assert seat.name == "Alice" and not seat.conflict


def test_reset_correction_requires_fresh_ocr_confirmation():
    state = TableState()
    state.update([player()], (1000, 600))
    state.correct(1, "Manual")
    state.correct(1, "")
    assert not state.update([player()], (1000, 600))[0].name
    assert state.update([player()], (1000, 600))[0].name == "Alice"


def test_cards_do_not_cover_other_player_rois_at_small_resolution():
    rois = [
        (396, 128, 110, 43),
        (686, 128, 110, 43),
        (205, 242, 110, 43),
        (875, 242, 110, 43),
        (830, 467, 110, 43),
        (540, 539, 110, 43),
    ]
    obstacles = list(rois)
    for roi in rois:
        box = place_card(roi, (1180, 688), (260, 96), obstacles)
        assert all(overlap(box, other) == 0 for other in obstacles)
        assert 0 <= box[0] <= 920 and 0 <= box[1] <= 592
        obstacles.append(box)


def test_dim_ocr_does_not_replace_an_established_identity():
    state = TableState()
    state.update([player()], (1000, 600))
    state.update([player()], (1000, 600))
    uncertain = player("A1ice")
    uncertain.confidence = 60
    for _ in range(4):
        seat = state.update([uncertain], (1000, 600))[0]
    assert seat.name == "Alice" and seat.conflict


def test_brief_ocr_loss_and_geometry_noise_preserve_identity():
    state = TableState()
    state.update([player()], (1000, 600))
    state.correct(1, "Alice")
    for _ in range(4):
        state.update([], (1000, 600))
    seat = state.update([player(x=102)], (1000, 600))[0]
    assert seat.key == 1 and seat.manual
    assert seat.display_roi[0] == 100
    assert seat.observation.roi[0] == 102


def test_persistent_alias_is_restored_and_accepts_both_spellings():
    state = TableState(lambda n: ("gh0st_", True) if n in {"ghOst_", "gh0st_"} else (n, False))
    state.update([player("ghOst_")], (1000, 600))
    seat = state.update([player("ghOst_")], (1000, 600))[0]
    assert seat.name == "gh0st_" and seat.manual
    assert not state.update([player("gh0st_")], (1000, 600))[0].conflict


def test_two_confident_typos_do_not_replace_established_name():
    state = TableState()
    for _ in range(2):
        state.update([player()], (1000, 600))
    for _ in range(2):
        state.update([player("A1ice")], (1000, 600))
    assert state.seats[1].name == "Alice"


def test_manual_name_survives_weak_primary_with_two_exact_ocr_views():
    state = TableState()
    state.update([player("")], (1000, 600))
    state.correct(1, "hmlssbliss")
    reading = player("hmlissbliss")
    reading.confidence = 49
    reading.ocr_candidates = (("hmlssbliss", 89), ("hmlssbliss", 76))
    seat = state.update([reading], (1000, 600))[0]
    assert seat.name == "hmlssbliss" and seat.manual and not seat.conflict
    # A confident competing identity still blocks the manually named player.
    reading.confidence = 90
    assert state.update([reading], (1000, 600))[0].conflict
    # One exact alternative or two weak ones cannot establish identity.
    reading.confidence = 49
    for alternatives in [(("hmlssbliss", 89),), (("hmlssbliss", 80), ("hmlssbliss", 76))]:
        reading.ocr_candidates = alternatives
        assert state.update([reading], (1000, 600))[0].conflict


def test_known_manual_identity_restored_from_exact_alternatives_after_departure():
    state = TableState(lambda n: (n, n == "hmlssbliss"))
    reading = player("hmlissbliss")
    reading.confidence = 49
    reading.ocr_candidates = (("hmlssbliss", 89), ("hmlssbliss", 76))
    assert not state.update([reading], (1000, 600))[0].manual
    seat = state.update([reading], (1000, 600))[0]
    assert seat.manual and seat.name == "hmlssbliss" and not seat.conflict
    for _ in range(10):
        state.update([], (1000, 600))
    assert not state.update([reading], (1000, 600))[0].manual
    assert state.update([reading], (1000, 600))[0].manual
    other = player("Other")
    other.ocr_candidates = reading.ocr_candidates
    assert state.update([other], (1000, 600))[0].conflict
