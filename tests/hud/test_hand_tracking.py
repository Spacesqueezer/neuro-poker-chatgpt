from poker.hud.hand import HandTracker, observe
from poker.hud.models import CardObservation, PlayerObservation
from poker.hud.presentation import GREEN, RED, YELLOW, name_color
from poker.hud.state import Seat


def cards(hero=("As", "Kd"), board=(), score=95):
    return [
        CardObservation(zone, (i * 100, 300, 90, 140), value, score)
        for zone, values in [("hero", hero), ("board", board)]
        for i, value in enumerate(values)
    ]


def test_streets_and_turn_signal():
    for board, street in [
        ((), "Префлоп"),
        (("2c", "3h", "4s"), "Флоп"),
        (("2c", "3h", "4s", "8c"), "Тёрн"),
        (("2c", "3h", "4s", "8c", "Qc"), "Ривер"),
    ]:
        hand = observe(cards(board=board), my_turn=True)
        assert hand.valid and hand.street == street and hand.phase == "Ваш ход"


def test_unknown_duplicate_and_low_confidence_cards_disable_odds():
    for hand_cards in [cards(("As", "")), cards(("As", "As")), cards(score=74)]:
        hand = observe(hand_cards)
        assert not hand.valid and hand.odds is None


def test_transition_requires_two_frames_and_does_not_reuse_previous_hand():
    tracker = HandTracker()
    assert not tracker.update(observe(cards()))
    assert tracker.update(observe(cards()))
    assert tracker.hand_number == 1
    assert not tracker.update(observe(cards(board=("2c", "3h", "4s"))))
    assert tracker.update(observe(cards(board=("2c", "3h", "4s"))))
    assert tracker.hand_number == 1
    assert not tracker.update(observe(cards(hero=("Qc", "Qh"))))
    assert tracker.update(observe(cards(hero=("Qc", "Qh"))))
    assert tracker.hand_number == 2


def test_one_missing_frame_does_not_create_a_new_hand():
    tracker = HandTracker()
    tracker.update(observe(cards()))
    tracker.update(observe(cards()))
    tracker.update(observe([]))
    tracker.update(observe(cards()))
    tracker.update(observe(cards()))
    assert tracker.hand_number == 1


def test_nickname_colors_and_manual_confirmation():
    observation = PlayerObservation((0, 0, 100, 40), "Alice", 95, "100", "recognized")
    seat = Seat(1, observation, name="Alice")
    assert name_color(seat) == GREEN
    observation.confidence = 89
    assert name_color(seat) == YELLOW
    observation.confidence = 64
    assert name_color(seat) == RED
    seat.manual = True
    assert name_color(seat) == GREEN
    seat.conflict = True
    assert name_color(seat) == RED


def test_lost_table_is_not_a_completed_hand():
    tracker = HandTracker()
    tracker.update(observe(cards()))
    tracker.update(observe(cards()))
    for _ in range(3):
        missing = observe([], table_found=False)
        assert not tracker.update(missing)
        assert missing.phase == "Стол не распознан"
        assert missing.street == "Неизвестно"
    assert not tracker.update(observe(cards()))
    assert tracker.update(observe(cards()))
    assert tracker.hand_number == 1
