from poker.api.hand_state import HandStateView, PublicPlayerView
from poker.statistics.collector import StatisticsCollector
from poker.statistics.database.facade import StatisticsFacade
from poker.statistics.database.memory import (
	MemoryAgentMemoryRepository,
	MemoryPlayerRepository,
	MemoryStatisticsRepository,
)
from poker.statistics.database.models import AgentMemoryRecord
from poker.statistics.database.services import StatisticsService
from poker.statistics.opponent_profile import OpponentProfileProvider
from poker.learning.observation import LearningObservationEncoder


def _state():
	return HandStateView(
		street="flop",
		acting_player="hero",
		hole_cards=("A♠", "K♠"),
		board=("2♣", "7♦", "J♥"),
		pot=20,
		target_bet=4,
		minimum_raise=4,
		dealer="villain",
		small_blind="hero",
		big_blind="villain",
		players=(
			PublicPlayerView(
				name="hero",
				chips=90,
				current_bet=2,
				total_contribution=10,
				folded=False,
				position="BB",
			),
			PublicPlayerView(
				name="villain",
				chips=80,
				current_bet=4,
				total_contribution=20,
				folded=False,
				position="BTN",
			),
		),
	)


def _profile_provider():
	service = StatisticsService(
		MemoryPlayerRepository(),
		MemoryStatisticsRepository(),
		MemoryAgentMemoryRepository(),
	)
	collector = StatisticsCollector()
	collector.register_hand(
		"villain",
		position="BTN",
		entered_pot=True,
		raised_preflop=True,
	)
	service.persist_collector(collector)
	player = service.get_player_by_name("villain")
	service.save_agent_memory(
		AgentMemoryRecord(
			agent_id="neural-a",
			player_id=player.id,
			hands_observed=12,
			vpip_estimate=0.40,
			pfr_estimate=0.25,
			aggression_estimate=1.2,
			confidence=0.7,
		)
	)
	return OpponentProfileProvider(StatisticsFacade(service))


def test_learning_observation_has_fixed_size_and_named_features():
	encoder = LearningObservationEncoder()
	observation = encoder.encode(
		_state(),
		profile_scope="global",
	)

	assert observation.size == encoder.size
	assert len(observation.feature_names) == encoder.size
	assert observation.feature_names[0:4] == (
		"street.preflop",
		"street.flop",
		"street.turn",
		"street.river",
	)
	assert observation.as_dict()["street.flop"] == 1.0
	assert observation.as_dict()["hole.A♠"] == 1.0
	assert observation.as_dict()["board.J♥"] == 1.0
	assert observation.opponent_order == ("villain",)


def test_unused_opponent_slots_are_zero_padded():
	encoder = LearningObservationEncoder()
	observation = encoder.encode(
		_state(),
		profile_scope="global",
	)
	values = observation.as_dict()

	assert values["opponent.0.present"] == 1.0
	assert values["opponent.1.present"] == 0.0
	assert values["opponent.7.present"] == 0.0
	assert values["opponent.7.profile.memory_confidence"] == 0.0


def test_private_scope_exposes_only_agent_memory_profile_features():
	encoder = LearningObservationEncoder(
		profile_provider=_profile_provider(),
	)
	observation = encoder.encode(
		_state(),
		agent_id="neural-a",
		profile_scope="private",
	)
	values = observation.as_dict()

	assert values["opponent.0.profile.vpip"] == 0.0
	assert values["opponent.0.profile.pfr"] == 0.0
	assert values["opponent.0.profile.position_vpip"] == 0.0
	assert values["opponent.0.profile.memory_hands_observed"] == 12.0
	assert values["opponent.0.profile.memory_vpip"] == 0.40
	assert values["opponent.0.profile.memory_confidence"] == 0.7


def test_global_scope_exposes_tracker_but_not_agent_memory():
	encoder = LearningObservationEncoder(
		profile_provider=_profile_provider(),
	)
	observation = encoder.encode(
		_state(),
		profile_scope="global",
	)
	values = observation.as_dict()

	assert values["opponent.0.profile.vpip"] == 1.0
	assert values["opponent.0.profile.pfr"] == 1.0
	assert values["opponent.0.profile.position_vpip"] == 1.0
	assert values["opponent.0.profile.memory_hands_observed"] == 0.0
	assert values["opponent.0.profile.memory_confidence"] == 0.0


def test_combined_scope_requires_agent_id_and_exposes_both_sources():
	encoder = LearningObservationEncoder(
		profile_provider=_profile_provider(),
	)

	try:
		encoder.encode(
			_state(),
			profile_scope="combined",
		)
	except ValueError as error:
		assert "agent_id is required" in str(error)
	else:
		raise AssertionError("Expected agent id validation")

	observation = encoder.encode(
		_state(),
		agent_id="neural-a",
		profile_scope="combined",
	)
	values = observation.as_dict()

	assert values["opponent.0.profile.vpip"] == 1.0
	assert values["opponent.0.profile.memory_vpip"] == 0.40


def test_unknown_cards_are_rejected_instead_of_silently_reencoded():
	state = _state()
	broken = HandStateView(
		street=state.street,
		acting_player=state.acting_player,
		hole_cards=("XX",),
		board=state.board,
		pot=state.pot,
		target_bet=state.target_bet,
		minimum_raise=state.minimum_raise,
		dealer=state.dealer,
		small_blind=state.small_blind,
		big_blind=state.big_blind,
		players=state.players,
	)

	try:
		LearningObservationEncoder().encode(
			broken,
			profile_scope="global",
		)
	except ValueError as error:
		assert "Unsupported card representation" in str(error)
	else:
		raise AssertionError("Expected card representation validation")
