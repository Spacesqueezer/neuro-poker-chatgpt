from poker.api import ActionDecision, HandStateView, LegalActions, PublicPlayerView
from poker.game.actions import PlayerAction
from poker.learning.sample import LearningSampleBuilder

class TeacherRecordImporter:
	def __init__(self, small_blind=1, big_blind=2, action_abstraction=None):
		self.small_blind = small_blind
		self.big_blind = big_blind
		self.action_abstraction = action_abstraction
		self.sample_builder = LearningSampleBuilder()

	def import_record(self, record):
		info = record["information_set"]

		# Reconstruction
		street = info["street"]
		acting_player = f"player_{info['player']}"

		# Card formatting
		def format_card(card):
			rank_map = {11: "J", 12: "Q", 13: "K", 14: "A"}
			rank = rank_map.get(card["rank"], str(card["rank"]))
			suit_map = {"C": "♣", "D": "♦", "H": "♥", "S": "♠"}
			suit = suit_map.get(card["suit"], card["suit"])
			return f"{rank}{suit}"

		hole_cards = tuple(format_card(card) for card in info["hole_cards"])
		board = tuple(format_card(card) for card in info["public_board"])

		commitments = info["commitments"]
		starting_stacks = info["starting_stacks"]

		pot = sum(commitments)
		target_bet = max(commitments)

		p0_chips = starting_stacks[0] - commitments[0]
		p1_chips = starting_stacks[1] - commitments[1]

		p0_folded = False
		p1_folded = False
		# In solver, terminal nodes aren't exported.

		players = (
			PublicPlayerView(
				name="player_0",
				chips=p0_chips,
				current_bet=commitments[0],
				total_contribution=commitments[0],
				folded=p0_folded,
				position="SB" if info["history"] and info["history"][0] == "fold" else "BTN", # Approximation
			),
			PublicPlayerView(
				name="player_1",
				chips=p1_chips,
				current_bet=commitments[1],
				total_contribution=commitments[1],
				folded=p1_folded,
				position="BB",
			)
		)

		# Approximation of minimum raise. In restricted holdem it's often fixed.
		minimum_raise = self.big_blind
		if self.action_abstraction:
			if street == "preflop":
				minimum_raise = self.action_abstraction["preflop_raise_bb"] * self.big_blind - target_bet

		hand_state = HandStateView(
			street=street,
			acting_player=acting_player,
			hole_cards=hole_cards,
			board=board,
			pot=pot,
			target_bet=target_bet,
			minimum_raise=max(0, minimum_raise),
			dealer="player_0",
			small_blind="player_0",
			big_blind="player_1",
			players=players,
			action_history=(), # Restricted solver info set doesn't track public action history exactly matching production
		)

		legal_actions_set = set()
		call_amount = 0
		min_bet = None
		max_bet = None
		min_raise_to = None
		max_raise_to = None

		for act in record["legal_actions"]:
			if act == "fold":
				legal_actions_set.add(PlayerAction.FOLD)
			elif act == "check":
				legal_actions_set.add(PlayerAction.CHECK)
			elif act == "call":
				legal_actions_set.add(PlayerAction.CALL)
				call_amount = target_bet - commitments[info["player"]]
			elif act == "all_in":
				legal_actions_set.add(PlayerAction.ALL_IN)
			elif act.startswith("bet_") or act == "bet":
				legal_actions_set.add(PlayerAction.BET)
				# Abstract
				min_bet = self.big_blind
				max_bet = starting_stacks[info["player"]]
			elif act.startswith("raise_") or act == "raise":
				legal_actions_set.add(PlayerAction.RAISE)
				min_raise_to = target_bet + self.big_blind
				max_raise_to = starting_stacks[info["player"]]
			elif act == "shove":
				legal_actions_set.add(PlayerAction.ALL_IN)

		legal_actions = LegalActions(
			actions=tuple(legal_actions_set),
			call_amount=call_amount,
			min_bet=min_bet,
			max_bet=max_bet,
			min_raise_to=min_raise_to,
			max_raise_to=max_raise_to,
		)

		best_action_str = max(record["strategy"].items(), key=lambda x: (x[1], -list(record["strategy"].keys()).index(x[0])))[0]

		action_enum = PlayerAction.FOLD
		amount = 0
		if best_action_str == "check":
			action_enum = PlayerAction.CHECK
		elif best_action_str == "call":
			action_enum = PlayerAction.CALL
			amount = call_amount
		elif best_action_str == "all_in" or best_action_str == "shove":
			action_enum = PlayerAction.ALL_IN
		elif best_action_str.startswith("bet"):
			action_enum = PlayerAction.BET
			amount = min_bet # Simple approximation for testing/building sample
		elif best_action_str.startswith("raise"):
			action_enum = PlayerAction.RAISE
			amount = min_raise_to

		decision = ActionDecision(action=action_enum, amount=amount)

		return self.sample_builder.build(
			hand_state,
			legal_actions,
			decision,
		)
