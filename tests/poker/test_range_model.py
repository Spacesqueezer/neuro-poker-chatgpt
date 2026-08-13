import random

from poker.agents.expert import full_deck
from poker.api.hand_state import PublicPlayerView
from poker.strategy.ranges import PositionRangeModel


def _player(position):
	return PublicPlayerView(
		name="villain",
		chips=100,
		current_bet=0,
		total_contribution=0,
		folded=False,
		position=position,
	)


def _average_rank(position, samples=1000):
	model = PositionRangeModel()
	rng = random.Random(123)
	deck = full_deck()
	total = 0

	for _ in range(samples):
		cards = model.sample_hole_cards(
			deck,
			_player(position),
			None,
			rng,
		)
		total += sum(card.rank.value for card in cards) / 2

	return total / samples


def test_early_position_range_is_tighter_than_button_range():
	utg = _average_rank("UTG")
	button = _average_rank("BTN")

	assert utg > button


def test_range_model_never_returns_duplicate_cards():
	model = PositionRangeModel()
	rng = random.Random(42)
	deck = full_deck()

	for _ in range(100):
		cards = model.sample_hole_cards(
			deck,
			_player("CO"),
			None,
			rng,
		)

		assert len(cards) == 2
		assert cards[0] != cards[1]
