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


class UniformRangeModel:
	def sample_hole_cards(self, available, player, state, rng):
		return tuple(rng.sample(available, 2))


class PositionRangeModel:
	def sample_hole_cards(self, available, player, state, rng):
		combos = list(combinations(available, 2))
		if not combos:
			raise ValueError("No opponent hole-card combinations available")

		exponent = _POSITION_EXPONENT.get(player.position, 2.5)
		weights = [
			self._weight(combo) ** exponent + 0.002
			for combo in combos
		]

		return tuple(
			rng.choices(
				combos,
				weights=weights,
				k=1,
			)[0]
		)

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
