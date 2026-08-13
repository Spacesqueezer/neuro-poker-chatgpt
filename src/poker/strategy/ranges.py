from dataclasses import dataclass
from itertools import combinations


_POSITION_EXPONENT = {
	"UTG": 4.5,
	"UTG+1": 4.0,
	"MP": 3.4,
	"LJ": 3.0,
	"HJ": 2.6,
	"CO": 2.1,
	"BTN": 1.7,
	"BTN/SB": 1.8,
	"SB": 2.4,
	"BB": 2.2,
}


@dataclass(frozen=True)
class OpponentRangeState:
	position: str
	preflop_calls: int = 0
	preflop_raise_level: int = 0
	preflop_all_in: bool = False
	preflop_aggression_ratio: float = 0.0
	flop_calls: int = 0
	flop_aggression: int = 0
	flop_aggression_ratio: float = 0.0
	turn_calls: int = 0
	turn_aggression: int = 0
	turn_aggression_ratio: float = 0.0
	river_calls: int = 0
	river_aggression: int = 0
	river_aggression_ratio: float = 0.0

	@property
	def preflop_action_class(self):
		if self.preflop_all_in:
			return "all_in"
		if self.preflop_raise_level >= 3:
			return "4bet_plus"
		if self.preflop_raise_level == 2:
			return "3bet"
		if self.preflop_raise_level == 1:
			return "open_raise"
		if self.preflop_calls:
			return "call"
		return "unopened"


class UniformRangeModel:
	def sample_hole_cards(self, available, player, state, rng):
		return tuple(rng.sample(available, 2))


class PositionRangeModel:
	def combo_distribution(self, available, player, state):
		combos = list(combinations(available, 2))
		if not combos:
			raise ValueError("No opponent hole-card combinations available")

		range_state = self.build_range_state(player, state)
		exponent = self._range_exponent_from_state(range_state)
		raw_weights = [
			(
				self._weight(combo) ** exponent
				* self._evidence_multiplier(combo, range_state)
			)
			+ 0.002
			for combo in combos
		]
		total = sum(raw_weights)

		return tuple(
			(combo, weight / total)
			for combo, weight in zip(combos, raw_weights)
		)

	def sample_hole_cards(self, available, player, state, rng):
		distribution = self.combo_distribution(available, player, state)
		combos = [combo for combo, _ in distribution]
		weights = [weight for _, weight in distribution]

		return tuple(
			rng.choices(
				combos,
				weights=weights,
				k=1,
			)[0]
		)

	def build_range_state(self, player, state):
		if state is None:
			return OpponentRangeState(position=player.position)

		preflop_calls = 0
		preflop_raise_level = 0
		preflop_all_in = False
		preflop_aggression_ratio = 0.0
		street_calls = {"flop": 0, "turn": 0, "river": 0}
		street_aggression = {"flop": 0, "turn": 0, "river": 0}
		street_aggression_ratio = {
			"flop": 0.0,
			"turn": 0.0,
			"river": 0.0,
		}
		preflop_raise_count = 0

		for action in state.action_history:
			if action.street == "preflop" and action.action in {"raise", "all_in"}:
				preflop_raise_count += 1

			if action.player != player.name:
				continue

			if action.street == "preflop":
				if action.action == "call":
					preflop_calls += 1
				elif action.action == "raise":
					preflop_raise_level = max(preflop_raise_level, preflop_raise_count)
					preflop_aggression_ratio = max(
						preflop_aggression_ratio,
						self._aggression_ratio(action),
					)
				elif action.action == "all_in":
					preflop_all_in = True
					preflop_raise_level = max(preflop_raise_level, preflop_raise_count)
					preflop_aggression_ratio = max(
						preflop_aggression_ratio,
						self._aggression_ratio(action),
					)
			elif action.street in street_calls:
				if action.action == "call":
					street_calls[action.street] += 1
				elif action.action in {"bet", "raise", "all_in"}:
					street_aggression[action.street] += 1
					street_aggression_ratio[action.street] = max(
						street_aggression_ratio[action.street],
						self._aggression_ratio(action),
					)

		return OpponentRangeState(
			position=player.position,
			preflop_calls=preflop_calls,
			preflop_raise_level=preflop_raise_level,
			preflop_all_in=preflop_all_in,
			preflop_aggression_ratio=preflop_aggression_ratio,
			flop_calls=street_calls["flop"],
			flop_aggression=street_aggression["flop"],
			flop_aggression_ratio=street_aggression_ratio["flop"],
			turn_calls=street_calls["turn"],
			turn_aggression=street_aggression["turn"],
			turn_aggression_ratio=street_aggression_ratio["turn"],
			river_calls=street_calls["river"],
			river_aggression=street_aggression["river"],
			river_aggression_ratio=street_aggression_ratio["river"],
		)

	def _range_exponent(self, player, state):
		return self._range_exponent_from_state(
			self.build_range_state(player, state)
		)

	def _range_exponent_from_state(self, range_state):
		exponent = _POSITION_EXPONENT.get(range_state.position, 2.5)
		exponent += {
			"unopened": 0.0,
			"call": 0.30,
			"open_raise": 1.00,
			"3bet": 2.00,
			"4bet_plus": 3.00,
			"all_in": 3.50,
		}[range_state.preflop_action_class]
		exponent += 0.20 * (range_state.flop_calls + range_state.turn_calls + range_state.river_calls)
		exponent += 0.70 * range_state.flop_aggression
		exponent += 0.90 * range_state.turn_aggression
		exponent += 1.10 * range_state.river_aggression
		return min(9.0, exponent)

	def _aggression_ratio(self, action):
		pot_before = max(1, action.pot - action.contributed)
		return action.contributed / pot_before

	def _evidence_multiplier(self, combo, range_state):
		first, second = combo
		high = max(first.rank.value, second.rank.value)
		low = min(first.rank.value, second.rank.value)
		pair = first.rank == second.rank
		suited = first.suit == second.suit
		gap = abs(first.rank.value - second.rank.value)

		premium_pair = pair and high >= 11
		medium_pair = pair and 7 <= high <= 10
		broadway = high >= 13 and low >= 10
		suited_ace = suited and high == 14
		suited_connector = suited and gap == 1 and high <= 11
		weak_offsuit = (
			not pair
			and not suited
			and high <= 10
			and low <= 7
		)

		action_class = range_state.preflop_action_class
		multiplier = 1.0

		if action_class == "call":
			if medium_pair:
				multiplier *= 1.18
			if suited_connector:
				multiplier *= 1.15
			if premium_pair:
				multiplier *= 0.92
		elif action_class == "open_raise":
			if broadway or suited_ace:
				multiplier *= 1.18
			if suited_connector:
				multiplier *= 1.10
		elif action_class == "3bet":
			if premium_pair:
				multiplier *= 1.55
			if broadway:
				multiplier *= 1.35
			if suited_ace:
				multiplier *= 1.22
			if suited_connector:
				multiplier *= 0.78
			if weak_offsuit:
				multiplier *= 0.55
		elif action_class == "4bet_plus":
			if premium_pair:
				multiplier *= 2.10
			if broadway:
				multiplier *= 1.50
			if suited_ace:
				multiplier *= 1.18
			if medium_pair:
				multiplier *= 0.72
			if suited_connector:
				multiplier *= 0.42
			if weak_offsuit:
				multiplier *= 0.25
		elif action_class == "all_in":
			if premium_pair:
				multiplier *= 2.50
			if broadway:
				multiplier *= 1.65
			if suited_ace:
				multiplier *= 1.20
			if medium_pair:
				multiplier *= 0.60
			if suited_connector:
				multiplier *= 0.32
			if weak_offsuit:
				multiplier *= 0.18

		pressure = min(2.0, range_state.preflop_aggression_ratio)
		if pressure > 0:
			if premium_pair:
				multiplier *= 1.0 + 0.30 * pressure
			elif broadway or suited_ace:
				multiplier *= 1.0 + 0.12 * pressure
			elif suited_connector or weak_offsuit:
				multiplier *= max(0.35, 1.0 - 0.22 * pressure)

		postflop_pressure = (
			0.50 * min(2.0, range_state.flop_aggression_ratio)
			+ 0.75 * min(2.0, range_state.turn_aggression_ratio)
			+ 1.00 * min(2.0, range_state.river_aggression_ratio)
		)
		if postflop_pressure > 0:
			if premium_pair or broadway:
				multiplier *= 1.0 + 0.08 * postflop_pressure
			if weak_offsuit:
				multiplier *= max(
					0.30,
					1.0 - 0.12 * postflop_pressure,
				)

		return max(0.05, multiplier)

	def _weight(self, combo):
		first, second = combo
		high = max(first.rank.value, second.rank.value)
		low = min(first.rank.value, second.rank.value)
		pair = first.rank == second.rank
		suited = first.suit == second.suit
		gap = abs(first.rank.value - second.rank.value)

		if pair:
			return min(
				1.0,
				0.50 + (high - 2) / 20,
			)

		score = (
			0.10
			+ (high - 2) / 24
			+ (low - 2) / 40
		)

		if suited:
			score += 0.10

		if gap == 1:
			score += 0.10
		elif gap == 2:
			score += 0.05

		if high >= 13 and low >= 10:
			score += 0.10

		return min(1.0, max(0.02, score))
