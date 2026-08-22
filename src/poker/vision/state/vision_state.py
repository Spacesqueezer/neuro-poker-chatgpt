from dataclasses import dataclass, field


@dataclass
class VisionState:
	is_table_found: bool = False
	is_my_turn: bool = False
	hero_seat: int | None = None
	hero_name: str | None = None
	street_name: str = "unknown"
	hero_cards: list[str] = field(default_factory=list)
	board_cards: list[str] = field(default_factory=list)
