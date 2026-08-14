from dataclasses import dataclass

from poker.solver import ExternalSamplingMCCFR


@dataclass(frozen=True)
class ChanceNode:
	state: str
	probability: float


class CountingChanceGame:
	def __init__(self):
		self.visits = []

	def initial_nodes(self):
		return (
			ChanceNode("common", 0.9),
			ChanceNode("rare", 0.1),
		)

	def is_terminal_node(self, state):
		return True

	def terminal_node_utility(self, state, player):
		self.visits.append((state, player))
		return 0.0

	def player_to_act(self, state):
		raise AssertionError("terminal root has no acting player")

	def information_set_for_node(self, state, player):
		raise AssertionError("terminal root has no information set")

	def legal_actions(self, state):
		return ()

	def next_node(self, state, action):
		raise AssertionError("terminal root has no child nodes")


def test_mccfr_samples_one_weighted_initial_node_per_iteration():
	game = CountingChanceGame()

	ExternalSamplingMCCFR(
		game,
		seed=42,
	).train(100)

	assert len(game.visits) == 200

	states = [
		state
		for state, player in game.visits
		if player == 0
	]
	assert states.count("common") > states.count("rare")
	assert "rare" in states
