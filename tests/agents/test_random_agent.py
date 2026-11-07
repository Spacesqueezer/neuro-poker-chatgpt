from poker.api.hand_state import LegalActions
from poker.game.actions import PlayerAction
from poker.agents.random_agent import RandomAgent


def test_random_agent_returns_legal_sized_aggressive_actions():
	legal = LegalActions(
		actions=(
			PlayerAction.BET,
			PlayerAction.RAISE,
		),
		min_bet=10,
		max_bet=20,
		min_raise_to=30,
		max_raise_to=50,
	)
	agent = RandomAgent(seed=7)

	for _ in range(100):
		decision = agent.choose_action(None, legal)
		assert legal.allows(
			decision.action,
			decision.amount,
		)
