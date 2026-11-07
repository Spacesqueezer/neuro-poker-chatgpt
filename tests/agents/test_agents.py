from poker.agents.calling_station import CallingStationAgent
from poker.agents.nit import NitAgent
from poker.agents.random_agent import RandomAgent


def test_baseline_agents_exist():
	assert RandomAgent
	assert CallingStationAgent
	assert NitAgent
