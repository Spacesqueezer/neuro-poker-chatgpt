import json
from pathlib import Path


STRATEGY_EXPORT_VERSION = 1


def serialize_card(card):
	return {
		"rank": card.rank.value,
		"suit": card.suit.value,
	}


def serialize_information_set(info_set):
	(
		player,
		hole_cards,
		street,
		public_board,
		history,
		commitments,
		starting_stacks,
	) = info_set

	return {
		"player": player,
		"hole_cards": [
			serialize_card(card)
			for card in hole_cards
		],
		"street": street,
		"public_board": [
			serialize_card(card)
			for card in public_board
		],
		"history": list(history),
		"commitments": list(commitments),
		"starting_stacks": list(starting_stacks),
	}


def build_strategy_export(
	result,
	game,
	*,
	seed,
	scenario,
	benchmark_version,
):
	entries = []

	for info_set, strategy in result.average_strategy.items():
		serialized_info = serialize_information_set(info_set)
		entries.append({
			"information_set": serialized_info,
			"strategy": {
				action: strategy[action]
				for action in sorted(strategy)
			},
		})

	entries.sort(
		key=lambda entry: json.dumps(
			entry["information_set"],
			sort_keys=True,
			separators=(",", ":"),
		)
	)

	abstraction = game.action_abstraction

	return {
		"format_version": STRATEGY_EXPORT_VERSION,
		"solver": "external_sampling_mccfr",
		"iterations": result.iterations,
		"seed": seed,
		"benchmark": {
			"version": benchmark_version,
			"scenario": scenario,
			"starting_stacks": list(game.starting_stacks),
			"small_blind": game.small_blind,
			"big_blind": game.big_blind,
		},
		"action_abstraction": {
			"preflop_raise_bb": abstraction.preflop_raise_bb,
			"postflop_bet_sizes_bb": list(
				abstraction.postflop_bet_sizes_bb
			),
			"postflop_raise_increment_multiplier": (
				abstraction.postflop_raise_increment_multiplier
			),
		},
		"information_set_count": len(entries),
		"average_strategy": entries,
	}


def write_strategy_export(payload, output):
	path = Path(output)
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(
		json.dumps(
			payload,
			indent=2,
			sort_keys=True,
		) + "\n",
		encoding="utf-8",
	)
