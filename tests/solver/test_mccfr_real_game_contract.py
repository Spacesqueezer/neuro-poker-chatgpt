from dataclasses import dataclass

from poker.solver import ExternalSamplingMCCFR


@dataclass
class Node:
	state: str
	probability: float = 1.0


class TinyGame:
	def initial_nodes(self):
		return [Node("root")]

	def is_terminal_node(self, state):
		return state == "terminal"

	def terminal_node_utility(self, state, player):
		return 1.0

	def player_to_act(self, state):
		return 0

	def information_set_for_node(self, state, player):
		return (player, state)

	def legal_actions(self, state):
		return ("stop",)

	def next_node(self, state, action):
		return "terminal"


def test_mccfr_trains_against_generic_solver_contract():
	result = ExternalSamplingMCCFR(
		TinyGame(),
		seed=42,
	).train(5)

	assert result.iterations == 5
	assert result.average_strategy
