"""Hand observations and conservative transitions between visible frames."""

from dataclasses import asdict, dataclass, field

from poker.hud.odds import validate

STREETS = {0: "Префлоп", 3: "Флоп", 4: "Тёрн", 5: "Ривер"}


@dataclass
class HandObservation:
    hero: tuple[str, ...] = ()
    board: tuple[str, ...] = ()
    street: str = "Неизвестно"
    phase: str = "Ожидание карт"
    valid: bool = False
    my_turn: bool = False
    issue: str = ""
    cards: list = field(default_factory=list)
    odds: dict | None = None

    def to_dict(self):
        return asdict(self)


def observe(cards, my_turn=False, table_found=True):
    hero = tuple(c.value for c in cards if c.zone == "hero")
    board = tuple(c.value for c in cards if c.zone == "board")
    state = HandObservation(
        hero, board, STREETS.get(len(board), "Неизвестно"), my_turn=my_turn, cards=cards
    )
    if not table_found:
        state.phase = "Стол не распознан"
        state.street = "Неизвестно"
    elif not hero and not board:
        state.phase = "Ожидание раздачи"
        state.street = "Неизвестно"
    elif not hero:
        state.phase = "Карты героя не видны"
    else:
        try:
            validate(hero, board)
            if any(c.confidence < 75 for c in cards if c.zone in ("hero", "board")):
                raise ValueError("Low card confidence")
            state.valid = True
        except ValueError as error:
            state.issue = str(error)
        state.phase = (
            ("Ваш ход" if my_turn else "Ожидание действий") if state.valid else "Проверка карт"
        )
    return state


class HandTracker:
    def __init__(self):
        self.previous = None
        self.candidate = None
        self.confirmations = 0
        self.hand_number = 0
        self.last_seen = None
        self.empty_frames = 0

    def update(self, state):
        key = (state.hero, state.board)
        if not state.valid:
            self.confirmations = 0
            self.candidate = None
            if state.phase == "Ожидание раздачи":
                self.empty_frames += 1
                if self.empty_frames >= 2:
                    if self.previous:
                        state.phase = "Раздача завершена / ожидание новой"
                    self.previous = None
            else:
                self.empty_frames = 0
            self.last_seen = state
            return False
        self.confirmations = self.confirmations + 1 if key == self.candidate else 1
        self.empty_frames = 0
        self.candidate = key
        confirmed = self.confirmations >= 2
        if confirmed:
            if (
                self.previous is None
                or state.hero != self.previous[0]
                or (state.board[: len(self.previous[1])] != self.previous[1])
            ):
                self.hand_number += 1
            self.previous = key
        self.last_seen = state
        return confirmed
