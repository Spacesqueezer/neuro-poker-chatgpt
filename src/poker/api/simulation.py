from poker.api.hand_state import ActionDecision, build_hand_state_view, get_legal_actions
from poker.game.dealer import Dealer
from poker.game.game_state import GameState
from poker.game.hand_controller import HandController
from poker.game.round_manager import GameStreet
from poker.player.player import Player

TERMINAL_STREETS = {GameStreet.SHOWDOWN, GameStreet.COMPLETE}


def play_hand(
	agents,
	seed,
	starting_stack=100,
	small_blind=1,
	big_blind=2,
	max_actions=500,
	dealer_name=None,
	starting_stacks=None,
	decision_observer=None,
):
	if len(agents) < 2:
		raise ValueError("At least two agents are required")

	player_names = list(agents)
	if starting_stacks is None:
		if starting_stack <= 0:
			raise ValueError("Starting stack must be positive")
		stacks = {name: starting_stack for name in player_names}
	else:
		if set(starting_stacks) != set(player_names):
			raise ValueError("Starting stacks must match agent names")
		if any(stack <= 0 for stack in starting_stacks.values()):
			raise ValueError("Starting stacks must be positive")
		stacks = dict(starting_stacks)

	state = GameState()
	for name in player_names:
		state.add_player(Player(name, stacks[name]))

	if dealer_name is not None:
		if dealer_name not in agents:
			raise ValueError(f"Unknown dealer: {dealer_name}")
		desired_index = player_names.index(dealer_name)
		state.dealer_button_index = (desired_index - 1) % len(player_names)

	controller = HandController(
		Dealer(seed=seed),
		small_blind=small_blind,
		big_blind=big_blind,
	)
	controller.start_hand(state)

	actions_taken = 0
	while state.round_manager.street not in TERMINAL_STREETS:
		player = controller.current_player(state)
		if player is None:
			raise RuntimeError("Non-terminal hand has no acting player")

		legal = get_legal_actions(state, controller, player)
		view = build_hand_state_view(state, controller, player)
		decision = agents[player.name].choose_action(view, legal)
		if not isinstance(decision, ActionDecision):
			raise TypeError("Agent must return ActionDecision")
		if not legal.allows(decision.action, decision.amount):
			raise ValueError(
				f"Illegal agent decision: {player.name} {decision.action.value} {decision.amount}"
			)

		if decision_observer is not None:
			decision_observer(
				view,
				legal,
				decision,
			)

		controller.process_action(state, decision.action, decision.amount)
		actions_taken += 1
		if actions_taken > max_actions:
			raise RuntimeError("Hand exceeded action limit")

	if controller.hand_history is None or controller.hand_history.result is None:
		raise RuntimeError("Completed hand has no HandHistory")
	return controller.hand_history
