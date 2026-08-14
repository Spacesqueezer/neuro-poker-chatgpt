from poker.agents.expert import ExpertAgent, full_deck
from poker.api.hand_state import HandStateView, PublicActionView, PublicPlayerView
from poker.statistics.opponent_profile import (
	AgentMemoryProfile,
	OpponentProfile,
	PositionProfile,
)
from poker.strategy.ranges import PositionRangeModel


class FakeProfileProvider:
	def __init__(self, profile):
		self.profile = profile
		self.calls = []

	def get(self, player_name, agent_id=None):
		self.calls.append((player_name, agent_id))
		return self.profile


def _player():
	return PublicPlayerView(
		name="villain",
		chips=100,
		current_bet=18,
		total_contribution=18,
		folded=False,
		position="CO",
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


def _state(actions, board=(), street="preflop"):
	return HandStateView(
		street=street,
		acting_player="hero",
		hole_cards=("2♣", "3♦"),
		board=board,
		pot=40,
		target_bet=18,
		minimum_raise=12,
		dealer="hero",
		small_blind="hero",
		big_blind="villain",
		players=(_player(),),
		action_history=actions,
	)


def _profile(
	name,
	hands,
	vpip,
	pfr,
	three_bet,
	flop_aggression=1.0,
	memory=None,
):
	return OpponentProfile(
		player_id=1,
		name=name,
		hands=hands,
		vpip=vpip,
		pfr=pfr,
		three_bet=three_bet,
		flop_aggression=flop_aggression,
		turn_aggression=flop_aggression,
		river_aggression=flop_aggression,
		positions=(
			PositionProfile(
				position="CO",
				hands=hands,
				vpip=vpip,
				pfr=pfr,
				three_bet=three_bet,
			),
		),
		memory=memory or AgentMemoryProfile(),
	)


def _weight(distribution, cards):
	target = set(cards)
	for combo, weight in distribution:
		if {str(card) for card in combo} == target:
			return weight
	raise AssertionError(f"Combo not found: {cards}")


def test_low_three_bet_profile_is_more_value_heavy_than_loose_three_bettor():
	actions = (
		_action("opener", "raise", 6, 16),
		_action("villain", "raise", 18, 34),
	)
	state = _state(actions)
	deck = full_deck()

	tight = PositionRangeModel(
		profile_provider=FakeProfileProvider(
			_profile(
				"villain",
				hands=500,
				vpip=0.18,
				pfr=0.14,
				three_bet=0.03,
			)
		)
	).combo_distribution(deck, _player(), state)
	loose = PositionRangeModel(
		profile_provider=FakeProfileProvider(
			_profile(
				"villain",
				hands=500,
				vpip=0.42,
				pfr=0.34,
				three_bet=0.18,
			)
		)
	).combo_distribution(deck, _player(), state)

	tight_ratio = (
		_weight(tight, {"A♣", "A♦"})
		/ _weight(tight, {"8♣", "7♣"})
	)
	loose_ratio = (
		_weight(loose, {"A♣", "A♦"})
		/ _weight(loose, {"8♣", "7♣"})
	)

	assert tight_ratio > loose_ratio


def test_high_aggression_profile_keeps_more_draws_in_flop_betting_range():
	board = ("A♠", "7♠", "2♦")
	actions = (
		_action("villain", "bet", 20, 40, street="flop"),
	)
	state = _state(actions, board=board, street="flop")
	deck = [
		card
		for card in full_deck()
		if str(card) not in set(board)
	]

	passive = PositionRangeModel(
		profile_provider=FakeProfileProvider(
			_profile(
				"villain",
				hands=500,
				vpip=0.22,
				pfr=0.18,
				three_bet=0.06,
				flop_aggression=0.5,
			)
		)
	).combo_distribution(deck, _player(), state)
	aggressive = PositionRangeModel(
		profile_provider=FakeProfileProvider(
			_profile(
				"villain",
				hands=500,
				vpip=0.30,
				pfr=0.24,
				three_bet=0.10,
				flop_aggression=4.0,
			)
		)
	).combo_distribution(deck, _player(), state)

	passive_draw_to_set = (
		_weight(passive, {"K♠", "Q♠"})
		/ _weight(passive, {"7♣", "7♥"})
	)
	aggressive_draw_to_set = (
		_weight(aggressive, {"K♠", "Q♠"})
		/ _weight(aggressive, {"7♣", "7♥"})
	)

	assert aggressive_draw_to_set > passive_draw_to_set


def test_profile_provider_influence_is_disabled_without_history():
	actions = (
		_action("opener", "raise", 6, 16),
		_action("villain", "raise", 18, 34),
	)
	state = _state(actions)
	deck = full_deck()
	profile = _profile(
		"villain",
		hands=0,
		vpip=0.90,
		pfr=0.90,
		three_bet=0.90,
	)
	with_profile = PositionRangeModel(
		profile_provider=FakeProfileProvider(profile)
	).combo_distribution(deck, _player(), state)
	without_profile = PositionRangeModel().combo_distribution(
		deck,
		_player(),
		state,
	)

	assert with_profile == without_profile


def test_expert_agent_builds_profile_aware_range_model():
	provider = FakeProfileProvider(
		_profile(
			"villain",
			hands=100,
			vpip=0.30,
			pfr=0.22,
			three_bet=0.09,
		)
	)

	agent = ExpertAgent(
		seed=42,
		equity_samples=10,
		profile_provider=provider,
		agent_id=7,
	)

	assert agent.equity.range_model.profile_provider is provider
	assert agent.equity.range_model.agent_id == 7
