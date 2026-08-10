from dataclasses import dataclass

from poker.cards.card import Card
from poker.enums import Rank, Suit
from poker.game.dealer import Dealer
from poker.game.game_state import GameState
from poker.game.hand_controller import HandController
from poker.player.player import Player


RANKS = {
	"2": Rank.TWO,
	"3": Rank.THREE,
	"4": Rank.FOUR,
	"5": Rank.FIVE,
	"6": Rank.SIX,
	"7": Rank.SEVEN,
	"8": Rank.EIGHT,
	"9": Rank.NINE,
	"10": Rank.TEN,
	"J": Rank.JACK,
	"Q": Rank.QUEEN,
	"K": Rank.KING,
	"A": Rank.ACE,
}

SUITS = {
	"C": Suit.CLUBS,
	"D": Suit.DIAMONDS,
	"H": Suit.HEARTS,
	"S": Suit.SPADES,
}


@dataclass(frozen=True)
class ManualScenario:
	name: str
	description: str
	players: tuple[tuple[str, int], ...]
	dealer_name: str
	hole_cards: dict[str, tuple[str, str]]
	board: tuple[str, str, str, str, str]
	hint: str


class ScriptedDealer(Dealer):
	def __init__(self, draw_sequence):
		self.draw_sequence = list(draw_sequence)

	def start_hand(self, game_state):
		# Deck.draw() снимает карту с конца списка, поэтому сценарий кладём в обратном порядке.
		game_state.deck.cards = list(reversed(self.draw_sequence))

		for player in game_state.players:
			player.reset_for_hand()

		for _ in range(2):
			for player in game_state.players:
				player.hand.add_card(game_state.deck.draw())


SCENARIOS = {
	"default": ManualScenario(
		name="default",
		description="Three equal stacks; general manual play.",
		players=(("Alice", 100), ("Bob", 100), ("Carol", 100)),
		dealer_name="Alice",
		hole_cards={
			"Alice": ("3S", "10S"),
			"Bob": ("9C", "6D"),
			"Carol": ("3C", "4D"),
		},
		board=("10C", "8C", "10H", "KH", "4C"),
		hint="Free play with equal 100-chip stacks.",
	),
	"headsup": ManualScenario(
		name="headsup",
		description="Heads-up button/blind order and postflop action order.",
		players=(("Alice", 100), ("Bob", 100)),
		dealer_name="Alice",
		hole_cards={
			"Alice": ("AS", "9D"),
			"Bob": ("KC", "QH"),
		},
		board=("2C", "7D", "10H", "JS", "3C"),
		hint="BTN is also SB; BTN acts first preflop, BB first postflop.",
	),
	"minraise": ManualScenario(
		name="minraise",
		description="Minimum full-raise tracking.",
		players=(("Alice", 100), ("Bob", 100), ("Carol", 100)),
		dealer_name="Alice",
		hole_cards={
			"Alice": ("AH", "AD"),
			"Bob": ("KC", "KD"),
			"Carol": ("QC", "QD"),
		},
		board=("2S", "5S", "8H", "JC", "3D"),
		hint="Try: raise 4; then a later raise must respect the last full raise size.",
	),
	"short-allin": ManualScenario(
		name="short-allin",
		description="Short stack all-in and action reopening rules.",
		players=(("Alice", 100), ("Bob", 13), ("Carol", 100)),
		dealer_name="Alice",
		hole_cards={
			"Alice": ("AS", "KS"),
			"Bob": ("7H", "7D"),
			"Carol": ("QH", "QC"),
		},
		board=("2S", "4S", "9C", "10D", "3H"),
		hint="Bob has only 13 chips; use this to probe short all-in/reopen behavior.",
	),
	"sidepot": ManualScenario(
		name="sidepot",
		description="Three unequal stacks with main pot, side pot and unmatched refund.",
		players=(("Alice", 20), ("Bob", 50), ("Carol", 100)),
		dealer_name="Alice",
		hole_cards={
			"Alice": ("AH", "AD"),
			"Bob": ("KH", "KD"),
			"Carol": ("QH", "QD"),
		},
		board=("2C", "5D", "8S", "JC", "3H"),
		hint="Target case: Alice all-in 20, Bob all-in 50, Carol all-in 100; expect main + side + unmatched refund.",
	),
	"splitpot": ManualScenario(
		name="splitpot",
		description="Forced board tie for split-pot payout testing.",
		players=(("Alice", 100), ("Bob", 100)),
		dealer_name="Alice",
		hole_cards={
			"Alice": ("2C", "3D"),
			"Bob": ("4C", "5D"),
		},
		board=("10H", "JH", "QH", "KH", "AH"),
		hint="Get both players to showdown; the royal-flush board forces an exact tie.",
	),
}


def parse_card(token):
	token = token.strip().upper()
	if len(token) < 2:
		raise ValueError(f"Invalid card: {token}")

	rank_text = token[:-1]
	suit_text = token[-1]
	if rank_text not in RANKS or suit_text not in SUITS:
		raise ValueError(f"Invalid card: {token}")

	return Card(RANKS[rank_text], SUITS[suit_text])


def scenario_names():
	return tuple(SCENARIOS)


def get_scenario(name):
	key = name.strip().lower()
	if key not in SCENARIOS:
		raise ValueError(f"Unknown scenario: {name}. Use 'scenario list'.")
	return SCENARIOS[key]


def create_scenario(name="default", small_blind=1, big_blind=2):
	scenario = get_scenario(name)
	state = GameState()
	for player_name, chips in scenario.players:
		state.add_player(Player(player_name, chips))

	draw_sequence = _build_draw_sequence(scenario)
	controller = HandController(
		ScriptedDealer(draw_sequence),
		small_blind=small_blind,
		big_blind=big_blind,
	)
	state.dealer_button_index = _dealer_index_before_start(state, scenario.dealer_name)
	controller.start_hand(state)
	return state, controller, scenario


def _dealer_index_before_start(state, dealer_name):
	desired_index = next(
		index
		for index, player in enumerate(state.players)
		if player.name == dealer_name
	)
	return (desired_index - 1) % len(state.players)


def _build_draw_sequence(scenario):
	sequence = []
	for card_index in range(2):
		for player_name, _ in scenario.players:
			sequence.append(parse_card(scenario.hole_cards[player_name][card_index]))

	# Burn, flop x3, burn, turn, burn, river.
	used_tokens = {
		card
		for cards in scenario.hole_cards.values()
		for card in cards
	} | set(scenario.board)
	burn_tokens = _unused_cards(used_tokens, 3)
	sequence.extend([
		parse_card(burn_tokens[0]),
		parse_card(scenario.board[0]),
		parse_card(scenario.board[1]),
		parse_card(scenario.board[2]),
		parse_card(burn_tokens[1]),
		parse_card(scenario.board[3]),
		parse_card(burn_tokens[2]),
		parse_card(scenario.board[4]),
	])
	return sequence


def _unused_cards(used_tokens, count):
	available = []
	for rank in ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"):
		for suit in ("C", "D", "H", "S"):
			token = f"{rank}{suit}"
			if token not in used_tokens:
				available.append(token)
				if len(available) == count:
					return available

	raise RuntimeError("Could not allocate burn cards")
