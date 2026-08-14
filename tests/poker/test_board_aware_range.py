from poker.agents.expert import full_deck
from poker.api.hand_state import HandStateView, PublicActionView, PublicPlayerView
from poker.strategy.ranges import PositionRangeModel


def _player():
	return PublicPlayerView(
		name="villain",
		chips=100,
		current_bet=0,
		total_contribution=0,
		folded=False,
		position="CO",
	)


def _action(street, action, contributed=20, pot=40):
	return PublicActionView(
		street=street,
		player="villain",
		action=action,
		contributed=contributed,
		bet_before=0,
		bet_after=contributed,
		pot=pot,
		target=contributed,
	)


def _state(board, street, actions=()):
	return HandStateView(
		street=street,
		acting_player="hero",
		hole_cards=("3♣", "4♦"),
		board=board,
		pot=40,
		target_bet=20,
		minimum_raise=20,
		dealer="hero",
		small_blind="hero",
		big_blind="villain",
		players=(_player(),),
		action_history=actions,
	)


def _available(board):
	blocked = set(board)
	return [
		card
		for card in full_deck()
		if str(card) not in blocked
	]


def _combo_weight(distribution, cards):
	target = set(cards)
	for combo, weight in distribution:
		if {str(card) for card in combo} == target:
			return weight
	raise AssertionError(f"Combo not found: {cards}")


def test_flop_bet_reweights_set_more_than_air():
	model = PositionRangeModel()
	board = ("A♣", "7♦", "2♠")
	passive = _state(board, "flop")
	aggressive = _state(
		board,
		"flop",
		(_action("flop", "bet"),),
	)
	available = _available(board)

	passive_distribution = model.combo_distribution(
		available,
		_player(),
		passive,
	)
	aggressive_distribution = model.combo_distribution(
		available,
		_player(),
		aggressive,
	)

	passive_set = _combo_weight(
		passive_distribution,
		{"7♣", "7♥"},
	)
	aggressive_set = _combo_weight(
		aggressive_distribution,
		{"7♣", "7♥"},
	)
	passive_air = _combo_weight(
		passive_distribution,
		{"9♣", "4♥"},
	)
	aggressive_air = _combo_weight(
		aggressive_distribution,
		{"9♣", "4♥"},
	)

	assert aggressive_set / passive_set > aggressive_air / passive_air


def test_flop_aggression_keeps_flush_draw_as_semibluff_evidence():
	model = PositionRangeModel()
	board = ("A♠", "7♠", "2♦")
	passive = _state(board, "flop")
	aggressive = _state(
		board,
		"flop",
		(_action("flop", "bet"),),
	)
	available = _available(board)

	passive_distribution = model.combo_distribution(
		available,
		_player(),
		passive,
	)
	aggressive_distribution = model.combo_distribution(
		available,
		_player(),
		aggressive,
	)

	passive_draw = _combo_weight(
		passive_distribution,
		{"K♠", "Q♠"},
	)
	aggressive_draw = _combo_weight(
		aggressive_distribution,
		{"K♠", "Q♠"},
	)
	passive_air = _combo_weight(
		passive_distribution,
		{"K♣", "8♥"},
	)
	aggressive_air = _combo_weight(
		aggressive_distribution,
		{"K♣", "8♥"},
	)

	assert aggressive_draw / passive_draw > aggressive_air / passive_air


def test_river_does_not_classify_missed_flush_draw_as_live_draw():
	model = PositionRangeModel()
	board = ("A♠", "7♠", "2♦", "J♣", "3♥")
	state = _state(board, "river")
	available = _available(board)
	distribution = model.combo_distribution(
		available,
		_player(),
		state,
	)
	combo = next(
		combo
		for combo, _ in distribution
		if {str(card) for card in combo} == {"K♠", "Q♠"}
	)

	interaction = model.combo_board_interaction(combo, state)

	assert interaction.flush is False
	assert interaction.flush_draw is False


def test_turn_straight_draw_is_detected():
	model = PositionRangeModel()
	board = ("9♣", "6♦", "2♠", "K♥")
	state = _state(board, "turn")
	available = _available(board)
	distribution = model.combo_distribution(
		available,
		_player(),
		state,
	)
	combo = next(
		combo
		for combo, _ in distribution
		if {str(card) for card in combo} == {"8♣", "7♥"}
	)

	interaction = model.combo_board_interaction(combo, state)

	assert interaction.straight is False
	assert interaction.straight_draw is True
