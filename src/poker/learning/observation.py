from dataclasses import dataclass

from poker.statistics.opponent_profile import OpponentProfileEncoder


RANKS = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
SUITS = ("♣", "♦", "♥", "♠")
CARD_INDEX = {
	f"{rank}{suit}": index
	for index, (rank, suit) in enumerate(
		(rank, suit)
		for rank in RANKS
		for suit in SUITS
	)
}
STREETS = ("preflop", "flop", "turn", "river")


@dataclass(frozen=True)
class LearningObservation:
	values: tuple[float, ...]
	feature_names: tuple[str, ...]
	acting_player: str
	opponent_order: tuple[str, ...]

	@property
	def size(self):
		return len(self.values)

	def as_dict(self):
		return dict(zip(self.feature_names, self.values))


class LearningObservationEncoder:
	MAX_PLAYERS = 9
	MAX_OPPONENTS = MAX_PLAYERS - 1
	PROFILE_SCOPES = {"private", "global", "combined"}

	def __init__(self, profile_provider=None, profile_encoder=None):
		self.profile_provider = profile_provider
		self.profile_encoder = profile_encoder or OpponentProfileEncoder()

	def encode(
		self,
		hand_state,
		agent_id=None,
		profile_scope="private",
	):
		if profile_scope not in self.PROFILE_SCOPES:
			raise ValueError(f"Unsupported profile scope: {profile_scope}")
		if profile_scope in {"private", "combined"} and self.profile_provider is not None:
			if not agent_id:
				raise ValueError(
					"agent_id is required for private or combined opponent profiles"
				)
		if len(hand_state.players) > self.MAX_PLAYERS:
			raise ValueError(
				f"Learning observation supports at most {self.MAX_PLAYERS} players"
			)

		total_chips = sum(
			player.chips + player.total_contribution
			for player in hand_state.players
		)
		scale = float(total_chips or 1)

		values = []
		names = []

		self._extend(
			values,
			names,
			(
				1.0 if hand_state.street == street else 0.0
				for street in STREETS
			),
			(f"street.{street}" for street in STREETS),
		)
		self._extend(
			values,
			names,
			self._encode_cards(hand_state.hole_cards),
			(f"hole.{card}" for card in CARD_INDEX),
		)
		self._extend(
			values,
			names,
			self._encode_cards(hand_state.board),
			(f"board.{card}" for card in CARD_INDEX),
		)

		acting = self._acting_player(hand_state)
		self._extend(
			values,
			names,
			(
				hand_state.pot / scale,
				hand_state.target_bet / scale,
				hand_state.minimum_raise / scale,
				acting.chips / scale,
				acting.current_bet / scale,
				acting.total_contribution / scale,
			),
			(
				"table.pot",
				"table.target_bet",
				"table.minimum_raise",
				"hero.chips",
				"hero.current_bet",
				"hero.total_contribution",
			),
		)

		opponents = tuple(
			player
			for player in hand_state.players
			if player.name != hand_state.acting_player
		)

		for slot in range(self.MAX_OPPONENTS):
			prefix = f"opponent.{slot}"
			if slot < len(opponents):
				player = opponents[slot]
				profile_values = self._profile_values(
					player,
					agent_id=agent_id,
					profile_scope=profile_scope,
				)
				slot_values = (
					1.0,
					1.0 if player.folded else 0.0,
					player.chips / scale,
					player.current_bet / scale,
					player.total_contribution / scale,
					*profile_values,
				)
			else:
				slot_values = (0.0,) * (5 + self.profile_encoder.size)

			slot_names = (
				f"{prefix}.present",
				f"{prefix}.folded",
				f"{prefix}.chips",
				f"{prefix}.current_bet",
				f"{prefix}.total_contribution",
				*(
					f"{prefix}.profile.{name}"
					for name in self.profile_encoder.FEATURE_NAMES
				),
			)
			self._extend(values, names, slot_values, slot_names)

		return LearningObservation(
			values=tuple(values),
			feature_names=tuple(names),
			acting_player=hand_state.acting_player,
			opponent_order=tuple(player.name for player in opponents),
		)

	@property
	def size(self):
		return (
			len(STREETS)
			+ len(CARD_INDEX)
			+ len(CARD_INDEX)
			+ 6
			+ self.MAX_OPPONENTS * (5 + self.profile_encoder.size)
		)

	def _profile_values(self, player, agent_id, profile_scope):
		if self.profile_provider is None:
			return (0.0,) * self.profile_encoder.size

		profile_agent_id = (
			agent_id
			if profile_scope in {"private", "combined"}
			else None
		)
		profile = self.profile_provider.get(
			player.name,
			agent_id=profile_agent_id,
		)
		if profile is None:
			return (0.0,) * self.profile_encoder.size

		encoded = self.profile_encoder.encode(
			profile,
			position=player.position,
		)

		if profile_scope == "combined":
			return encoded
		if profile_scope == "global":
			return encoded[:17] + (0.0,) * 5

		return (0.0,) * 17 + encoded[17:]

	def _acting_player(self, hand_state):
		for player in hand_state.players:
			if player.name == hand_state.acting_player:
				return player

		raise ValueError(
			f"Acting player is missing from public player view: {hand_state.acting_player}"
		)

	def _encode_cards(self, cards):
		values = [0.0] * len(CARD_INDEX)

		for card in cards:
			if card not in CARD_INDEX:
				raise ValueError(f"Unsupported card representation: {card}")
			values[CARD_INDEX[card]] = 1.0

		return tuple(values)

	def _extend(self, values, names, new_values, new_names):
		new_values = tuple(float(value) for value in new_values)
		new_names = tuple(new_names)

		if len(new_values) != len(new_names):
			raise ValueError("Observation values and feature names are out of sync")

		values.extend(new_values)
		names.extend(new_names)
