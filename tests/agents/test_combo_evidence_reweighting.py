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


def _state(actions=()):
	return HandStateView(
		street="preflop",
		acting_player="hero",
		hole_cards=("2♣", "3♦"),
		board=(),
		pot=10,
		target_bet=4,
		minimum_raise=2,
		dealer="hero",
		small_blind="hero",
		big_blind="villain",
		players=(_player(),),
		action_history=actions,
	)


def _action(player, action, contributed, pot, street="preflop"):
	return PublicActionView(
		street=street,
		player=player,
		action=action,
		contributed=contributed,
		bet_before=0,
		bet_after=contributed,
		pot=pot,
		target=contributed,
	)


def _find_combo(distribution, first_rank, second_rank, suited=None):
	for combo, weight in distribution:
		ranks = sorted(
			(card.rank.value for card in combo),
			reverse=True,
		)
		if ranks != sorted(
			(first_rank, second_rank),
			reverse=True,
		):
			continue

		is_suited = combo[0].suit == combo[1].suit
		if suited is None or suited == is_suited:
			return weight

	raise AssertionError(
		f"Combo not found: {first_rank}, {second_rank}, suited={suited}"
	)


def test_3bet_reweights_premium_pair_more_than_suited_connector():
	model = PositionRangeModel()
	deck = full_deck()
	open_state = _state((
		_action("villain", "raise", 6, 16),
	))
	three_bet_state = _state((
		_action("opener", "raise", 6, 16),
		_action("villain", "raise", 18, 34),
	))

	open_distribution = model.combo_distribution(
		deck,
		_player(),
		open_state,
	)
	three_bet_distribution = model.combo_distribution(
		deck,
		_player(),
		three_bet_state,
	)

	open_aces = _find_combo(open_distribution, 14, 14)
	three_bet_aces = _find_combo(three_bet_distribution, 14, 14)
	open_connector = _find_combo(open_distribution, 8, 7, suited=True)
	three_bet_connector = _find_combo(
		three_bet_distribution,
		8,
		7,
		suited=True,
	)

	assert three_bet_aces / open_aces > three_bet_connector / open_connector


def test_larger_3bet_sizing_pushes_more_weight_toward_premium_pairs():
	model = PositionRangeModel()
	deck = full_deck()
	small = _state((
		_action("opener", "raise", 6, 16),
		_action("villain", "raise", 12, 28),
	))
	large = _state((
		_action("opener", "raise", 6, 16),
		_action("villain", "raise", 30, 46),
	))

	small_distribution = model.combo_distribution(
		deck,
		_player(),
		small,
	)
	large_distribution = model.combo_distribution(
		deck,
		_player(),
		large,
	)

	small_aces = _find_combo(small_distribution, 14, 14)
	large_aces = _find_combo(large_distribution, 14, 14)
	small_connector = _find_combo(
		small_distribution,
		8,
		7,
		suited=True,
	)
	large_connector = _find_combo(
		large_distribution,
		8,
		7,
		suited=True,
	)

	assert large_aces / small_aces > large_connector / small_connector


def test_range_state_keeps_public_aggression_sizing_evidence():
	model = PositionRangeModel()
	state = _state((
		_action("opener", "raise", 6, 16),
		_action("villain", "raise", 18, 34),
		_action("villain", "bet", 20, 54, street="flop"),
	))

	range_state = model.build_range_state(
		_player(),
		state,
	)

	assert range_state.preflop_action_class == "3bet"
	assert range_state.preflop_aggression_ratio > 0
	assert range_state.flop_aggression == 1
	assert range_state.flop_aggression_ratio > 0
