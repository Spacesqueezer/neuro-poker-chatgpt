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
		hole_cards=("A♠", "K♠"),
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


def _raise(player):
	return PublicActionView(
		street="preflop",
		player=player,
		action="raise",
		contributed=6,
		bet_before=2,
		bet_after=8,
		pot=11,
		target=8,
	)


def _combo_key(combo):
	return tuple(sorted(str(card) for card in combo))


def test_combo_distribution_is_normalized_and_complete():
	model = PositionRangeModel()
	available = full_deck()[:8]
	distribution = model.combo_distribution(available, _player(), _state())

	assert len(distribution) == 28
	assert abs(sum(weight for _, weight in distribution) - 1.0) < 1e-12
	assert all(weight > 0 for _, weight in distribution)


def test_combo_distribution_changes_after_observed_3bet():
	model = PositionRangeModel()
	available = full_deck()
	open_state = _state((_raise("villain"),))
	three_bet_state = _state((_raise("opener"), _raise("villain")))

	open_weights = {
		_combo_key(combo): weight
		for combo, weight in model.combo_distribution(available, _player(), open_state)
	}
	three_bet_weights = {
		_combo_key(combo): weight
		for combo, weight in model.combo_distribution(available, _player(), three_bet_state)
	}

	strongest = max(
		open_weights,
		key=lambda combo: model._weight(
			next(cards for cards in (item for item, _ in model.combo_distribution(available, _player(), open_state)) if _combo_key(cards) == combo)
		),
	)
	weakest = min(
		open_weights,
		key=lambda combo: model._weight(
			next(cards for cards in (item for item, _ in model.combo_distribution(available, _player(), open_state)) if _combo_key(cards) == combo)
		),
	)

	assert three_bet_weights[strongest] > open_weights[strongest]
	assert three_bet_weights[weakest] < open_weights[weakest]


def test_distribution_excludes_unavailable_cards():
	model = PositionRangeModel()
	available = full_deck()[:6]
	distribution = model.combo_distribution(available, _player(), _state())
	allowed = set(available)

	assert all(set(combo) <= allowed for combo, _ in distribution)
