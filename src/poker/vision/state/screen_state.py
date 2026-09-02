from dataclasses import dataclass, asdict


@dataclass
class VisionScreenState:
	is_my_turn: bool
	street_name: str
	board_cards: list
	hero_hole_cards: list
	total_pot: float | None
	can_fold: bool
	can_check: bool
	can_call: bool
	can_bet: bool
	can_raise: bool
	can_all_in: bool

	def to_dict(self):
		return asdict(
			self
		)


def street_from_board(
	board_cards,
):
	count = len(board_cards)

	if count == 0:
		return "preflop"

	if count == 3:
		return "flop"

	if count == 4:
		return "turn"

	if count == 5:
		return "river"

	return "unknown"
