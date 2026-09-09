from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ScreenPlayer:
    seat_index: int
    name: str
    is_active: bool
    is_dealer: bool
    stack: float
    current_bet: float
    cards_dealt: bool  # Если True, у игрока есть карты на руках (значит он не в пас)


@dataclass(frozen=True)
class ScreenState:
    """Shared screen observation; missing OCR amounts remain unknown."""

    is_my_turn: bool
    street_name: str  # "preflop", "flop", "turn", "river"
    board_cards: list[str]  # e.g. ["A♠", "K♥", "2♦"]
    hero_hole_cards: list[str]  # e.g. ["7♣", "8♣"]

    total_pot: float | None
    call_amount_needed: float | None = None
    min_raise_amount: float | None = None
    max_raise_amount: float | None = None

    players: list[ScreenPlayer] = field(default_factory=list)

    # Доступные кнопки на экране (чтобы не нажать то, чего нет)
    can_fold: bool = False
    can_check: bool = False
    can_call: bool = False
    can_bet: bool = False
    can_raise: bool = False
    can_all_in: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def street_from_board(board_cards: list[str]) -> str:
    return {0: "preflop", 3: "flop", 4: "turn", 5: "river"}.get(len(board_cards), "unknown")
