from dataclasses import dataclass, field
from typing import Optional, List, Dict

@dataclass(frozen=True)
class ScreenPlayer:
    seat_index: int
    name: str
    is_active: bool
    is_dealer: bool
    stack: float
    current_bet: float
    cards_dealt: bool # Если True, у игрока есть карты на руках (значит он не в пас)

@dataclass(frozen=True)
class ScreenState:
    """
    Сырое представление того, что распознано на экране.
    В будущем этот класс будет заполняться модулем OpenCV/Tesseract.
    """
    is_my_turn: bool
    street_name: str # "preflop", "flop", "turn", "river"
    board_cards: List[str] # e.g. ["A♠", "K♥", "2♦"]
    hero_hole_cards: List[str] # e.g. ["7♣", "8♣"]

    total_pot: float
    call_amount_needed: float
    min_raise_amount: float
    max_raise_amount: float

    players: List[ScreenPlayer] = field(default_factory=list)

    # Доступные кнопки на экране (чтобы не нажать то, чего нет)
    can_fold: bool = False
    can_check: bool = False
    can_call: bool = False
    can_bet: bool = False
    can_raise: bool = False
    can_all_in: bool = False
