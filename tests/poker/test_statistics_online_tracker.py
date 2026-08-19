from unittest.mock import MagicMock
from poker.statistics.online_tracker import OnlineMemoryTracker
from poker.statistics.database.models import AgentMemoryRecord, PlayerRecord

def test_online_memory_tracker_updates_agent_memory():
	facade = MagicMock()

	# Mock player records
	player_records = {
		"agent_0": PlayerRecord(id=1, name="agent_0"),
		"agent_1": PlayerRecord(id=2, name="agent_1"),
	}
	facade.get_player_by_name.side_effect = lambda name: player_records.get(name)

	# Mock memory return (None for first time)
	facade.get_opponent_memory.return_value = None

	mapper = MagicMock()
	mapper.map_hand.return_value = {
		"players": [
			{
				"name": "agent_0",
				"entered_pot": True,
				"raised_preflop": True,
				"aggressive_actions": 2,
				"calls": 1
			},
			{
				"name": "agent_1",
				"entered_pot": False,
				"raised_preflop": False,
				"aggressive_actions": 0,
				"calls": 0
			}
		]
	}

	tracker = OnlineMemoryTracker(statistics_facade=facade, mapper=mapper)

	tracker.process_hand(MagicMock()) # dummy hand history

	# Both agents should update memory for each other
	assert facade.save_opponent_memory.call_count == 2

	# Check agent_1's memory of agent_0
	calls = facade.save_opponent_memory.call_args_list
	saved_memories = [call[0][0] for call in calls]

	memory_of_agent_0 = next(m for m in saved_memories if m.player_id == 1)
	assert memory_of_agent_0.agent_id == "agent_1"
	assert memory_of_agent_0.hands_observed == 1
	assert memory_of_agent_0.vpip_estimate == 1.0 # agent_0 entered pot
	assert memory_of_agent_0.pfr_estimate == 1.0 # agent_0 raised preflop
	assert memory_of_agent_0.aggression_estimate == 2.0 # 2 aggressive actions / 1 call
	assert memory_of_agent_0.confidence == 0.001

	memory_of_agent_1 = next(m for m in saved_memories if m.player_id == 2)
	assert memory_of_agent_1.agent_id == "agent_0"
	assert memory_of_agent_1.hands_observed == 1
	assert memory_of_agent_1.vpip_estimate == 0.0 # agent_1 did not enter pot
	assert memory_of_agent_1.pfr_estimate == 0.0
	assert memory_of_agent_1.aggression_estimate == 0.0

def test_online_memory_tracker_skips_unknown_players():
	facade = MagicMock()
	facade.get_player_by_name.return_value = None # Player not in DB

	mapper = MagicMock()
	mapper.map_hand.return_value = {
		"players": [
			{"name": "agent_0"},
			{"name": "unknown_player"}
		]
	}

	tracker = OnlineMemoryTracker(statistics_facade=facade, mapper=mapper)
	tracker.process_hand(MagicMock())

	assert facade.save_opponent_memory.call_count == 0
