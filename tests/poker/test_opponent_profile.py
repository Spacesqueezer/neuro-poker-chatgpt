from poker.statistics.collector import StatisticsCollector
from poker.statistics.database.facade import StatisticsFacade
from poker.statistics.database.memory import (
	MemoryAgentMemoryRepository,
	MemoryPlayerRepository,
	MemoryStatisticsRepository,
)
from poker.statistics.database.models import AgentMemoryRecord
from poker.statistics.database.services import StatisticsService
from poker.statistics.opponent_profile import (
	OpponentProfileEncoder,
	OpponentProfileProvider,
)


def _service():
	return StatisticsService(
		MemoryPlayerRepository(),
		MemoryStatisticsRepository(),
		MemoryAgentMemoryRepository(),
	)


def _provider():
	service = _service()
	return service, OpponentProfileProvider(StatisticsFacade(service))


def test_profile_provider_returns_none_for_unknown_player():
	_, provider = _provider()

	assert provider.get("unknown") is None


def test_profile_provider_builds_tracker_snapshot():
	service, provider = _provider()
	collector = StatisticsCollector()

	collector.register_hand(
		"alice",
		position="CO",
		entered_pot=True,
		raised_preflop=True,
		three_bet_opportunity=True,
		three_bet=True,
		cbet_opportunity=True,
		cbet=True,
		fold_to_cbet_opportunity=True,
		folded_to_cbet=True,
		flop_aggressive_actions=2,
		flop_calls=1,
		turn_aggressive_actions=1,
		river_calls=1,
		showdown=True,
		won_showdown=True,
	)
	service.persist_collector(collector)

	profile = provider.get("alice")

	assert profile.name == "alice"
	assert profile.hands == 1
	assert profile.vpip == 1.0
	assert profile.pfr == 1.0
	assert profile.three_bet == 1.0
	assert profile.cbet == 1.0
	assert profile.fold_to_cbet == 1.0
	assert profile.flop_aggression == 2.0
	assert profile.turn_aggression == 1.0
	assert profile.river_aggression == 0.0
	assert profile.wtsd == 1.0
	assert profile.wsd == 1.0

	co = profile.position("CO")
	assert co is not None
	assert co.hands == 1
	assert co.vpip == 1.0
	assert co.pfr == 1.0
	assert co.three_bet == 1.0


def test_profile_keeps_agent_memory_separate_for_same_opponent():
	service, provider = _provider()
	collector = StatisticsCollector()
	collector.register_hand("alice", entered_pot=True)
	service.persist_collector(collector)

	player = service.get_player_by_name("alice")
	service.save_agent_memory(
		AgentMemoryRecord(
			agent_id="neural-a",
			player_id=player.id,
			hands_observed=20,
			vpip_estimate=0.35,
			pfr_estimate=0.20,
			aggression_estimate=1.5,
			confidence=0.8,
		)
	)
	service.save_agent_memory(
		AgentMemoryRecord(
			agent_id="neural-b",
			player_id=player.id,
			hands_observed=5,
			vpip_estimate=0.60,
			pfr_estimate=0.10,
			aggression_estimate=0.5,
			confidence=0.3,
		)
	)

	first = provider.get("alice", agent_id="neural-a")
	second = provider.get("alice", agent_id="neural-b")

	assert first.player_id == second.player_id
	assert first.memory.hands_observed == 20
	assert first.memory.vpip_estimate == 0.35
	assert first.memory.confidence == 0.8
	assert second.memory.hands_observed == 5
	assert second.memory.vpip_estimate == 0.60
	assert second.memory.confidence == 0.3


def test_encoder_has_stable_named_shape_and_position_fallback():
	service, provider = _provider()
	collector = StatisticsCollector()
	collector.register_hand(
		"alice",
		position="BTN",
		entered_pot=True,
	)
	service.persist_collector(collector)

	profile = provider.get("alice")
	encoder = OpponentProfileEncoder()

	btn = encoder.encode(profile, position="BTN")
	unknown = encoder.encode(profile, position="UTG")

	assert len(btn) == encoder.size
	assert encoder.size == 22
	assert encoder.size == len(encoder.FEATURE_NAMES)
	assert encoder.FEATURE_NAMES[13:17] == (
		"position_hands",
		"position_vpip",
		"position_pfr",
		"position_three_bet",
	)
	assert btn[13:17] == (1.0, 1.0, 0.0, 0.0)
	assert unknown[13:17] == (0.0, 0.0, 0.0, 0.0)
	assert unknown[-5:] == (0.0, 0.0, 0.0, 0.0, 0.0)
