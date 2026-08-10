from dataclasses import dataclass


@dataclass(frozen=True)
class PotLayer:
	kind: str
	amount: int
	eligible_players: tuple
	winners: tuple


@dataclass(frozen=True)
class PotSettlement:
	payouts: dict
	refunds: dict
	winners: tuple
	layers: tuple[PotLayer, ...]


class PotManager:
	def build_layers(self, players):
		contributions = {
			player: player.total_contribution
			for player in players
			if player.total_contribution > 0
		}
		if not contributions:
			return []

		levels = sorted(set(contributions.values()))
		previous_level = 0
		layers = []

		for level in levels:
			contributors = tuple(
				player
				for player, contribution in contributions.items()
				if contribution >= level
			)
			amount = (level - previous_level) * len(contributors)
			if amount > 0:
				layers.append((amount, contributors))
			previous_level = level

		return layers

	def settle(self, players, dealer_button_index, results, fallback_pot=0):
		payouts = {player: 0 for player in results}
		refunds = {}
		winners = []
		settled_layers = []

		layers = self.build_layers(players)
		if not layers and fallback_pot > 0:
			layers = [(fallback_pot, tuple(results))]

		for amount, contributors in layers:
			if amount <= 0:
				continue

			if len(contributors) == 1:
				player = contributors[0]
				player.chips += amount
				payouts[player] = payouts.get(player, 0) + amount
				refunds[player] = refunds.get(player, 0) + amount
				settled_layers.append(PotLayer("refund", amount, (player,), (player,)))
				continue

			eligible = tuple(player for player in contributors if not player.folded)
			if not eligible:
				raise RuntimeError("Pot layer has no eligible player")

			best_key = max(
				(results[player].rank, results[player].tiebreaker)
				for player in eligible
			)
			layer_winners = [
				player
				for player in eligible
				if (results[player].rank, results[player].tiebreaker) == best_key
			]
			ordered_winners = self._order_left_of_dealer(players, dealer_button_index, layer_winners)
			share, remainder = divmod(amount, len(ordered_winners))

			for index, player in enumerate(ordered_winners):
				payout = share + (1 if index < remainder else 0)
				player.chips += payout
				payouts[player] = payouts.get(player, 0) + payout
				if player not in winners:
					winners.append(player)

			settled_layers.append(PotLayer("pot", amount, eligible, tuple(ordered_winners)))

		return PotSettlement(
			payouts=payouts,
			refunds=refunds,
			winners=tuple(winners),
			layers=tuple(settled_layers),
		)

	def _order_left_of_dealer(self, players, dealer_button_index, winners):
		winner_set = set(winners)
		ordered = []
		player_count = len(players)

		for offset in range(1, player_count + 1):
			index = (dealer_button_index + offset) % player_count
			player = players[index]
			if player in winner_set:
				ordered.append(player)

		return ordered
