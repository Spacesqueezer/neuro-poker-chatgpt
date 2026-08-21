from dataclasses import dataclass

from poker.game.actions import PlayerAction
from poker.game.positions import positions_by_player


@dataclass(frozen=True)
class PublicPlayerView:
	name: str
	chips: int
	current_bet: int
	total_contribution: int
	folded: bool
	position: str


@dataclass(frozen=True)
class PublicActionView:
	street: str
	player: str
	action: str
	contributed: int
	bet_before: int
	bet_after: int
	pot: int
	target: int


@dataclass(frozen=True)
class HandStateView:
	street: str
	acting_player: str
	hole_cards: tuple[str, ...]
	board: tuple[str, ...]
	pot: int
	target_bet: int
	minimum_raise: int
	dealer: str
	small_blind: str
	big_blind: str
	players: tuple[PublicPlayerView, ...]
	action_history: tuple[PublicActionView, ...] = ()


@dataclass(frozen=True)
class LegalActions:
	actions: tuple[PlayerAction, ...]
	call_amount: int = 0
	min_bet: int | None = None
	max_bet: int | None = None
	min_raise_to: int | None = None
	max_raise_to: int | None = None

	def allows(self, action, amount=0):
		if action not in self.actions:
			return False
		if action == PlayerAction.BET:
			return (
				self.min_bet is not None
				and self.max_bet is not None
				and self.min_bet <= amount <= self.max_bet
			)
		if action == PlayerAction.RAISE:
			return (
				self.min_raise_to is not None
				and self.max_raise_to is not None
				and self.min_raise_to <= amount <= self.max_raise_to
			)
		if action == PlayerAction.CALL:
			return amount == 0 or amount == self.call_amount
		return amount == 0


@dataclass(frozen=True)
class ActionDecision:
	action: PlayerAction
	amount: int = 0


def build_hand_state_view(game_state, controller, player=None):
	player = player or controller.current_player(game_state)
	if player is None:
		raise RuntimeError("No player available to view state")

	dealer = game_state.players[game_state.dealer_button_index]
	small_blind = game_state.players[controller.small_blind_index]
	big_blind = game_state.players[controller.big_blind_index]
	positions = positions_by_player(
		game_state.players,
		game_state.dealer_button_index,
	)
	action_history = _public_action_history(controller)

	return HandStateView(
		street=game_state.round_manager.street.value,
		acting_player=player.name,
		hole_cards=tuple(str(card) for card in player.hand.cards),
		board=tuple(str(card) for card in game_state.board.cards),
		pot=controller.total_pot(game_state),
		target_bet=game_state.betting.current_bet,
		minimum_raise=controller.minimum_raise,
		dealer=dealer.name,
		small_blind=small_blind.name,
		big_blind=big_blind.name,
		players=tuple(
			PublicPlayerView(
				name=item.name,
				chips=item.chips,
				current_bet=item.current_bet,
				total_contribution=item.total_contribution,
				folded=item.folded,
				position=positions[item.name],
			)
			for item in game_state.players
		),
		action_history=action_history,
	)


def _public_action_history(controller):
	history = getattr(controller, "hand_history", None)
	if history is None:
		return ()

	return tuple(
		PublicActionView(
			street=event.data["street"],
			player=event.data["player"],
			action=event.data["action"],
			contributed=event.data["contributed"],
			bet_before=event.data["bet_before"],
			bet_after=event.data["bet_after"],
			pot=event.data["pot"],
			target=event.data["target"],
		)
		for event in history.events
		if event.type == "action"
	)


def get_legal_actions(game_state, controller, player=None):
	player = player or controller.current_player(game_state)
	if player is None or player.chips <= 0:
		return LegalActions(actions=())
	if player is not controller.current_player(game_state):
		raise ValueError("Legal actions are only available for the acting player")

	target = game_state.betting.current_bet
	facing = max(0, target - player.current_bet)
	max_target = player.current_bet + player.chips
	available = []
	call_amount = 0
	min_bet = None
	max_bet = None
	min_raise_to = None
	max_raise_to = None

	if facing > 0:
		available.append(PlayerAction.FOLD)
		available.append(PlayerAction.CALL)
		call_amount = min(facing, player.chips)
	else:
		available.append(PlayerAction.CHECK)

	if target == 0 and player.chips >= controller.big_blind:
		available.append(PlayerAction.BET)
		min_bet = controller.big_blind
		max_bet = player.chips

	if target > 0 and controller.betting_round.can_raise(
		player,
		current_target=target,
		minimum_raise=controller.minimum_raise,
	):
		minimum_target = target + controller.minimum_raise
		if max_target >= minimum_target:
			available.append(PlayerAction.RAISE)
			min_raise_to = minimum_target
			max_raise_to = max_target

	available.append(PlayerAction.ALL_IN)

	return LegalActions(
		actions=tuple(available),
		call_amount=call_amount,
		min_bet=min_bet,
		max_bet=max_bet,
		min_raise_to=min_raise_to,
		max_raise_to=max_raise_to,
	)
