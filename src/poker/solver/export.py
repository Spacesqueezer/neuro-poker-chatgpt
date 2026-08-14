import json
from pathlib import Path


STRATEGY_EXPORT_VERSION = 1
SUPPORTED_SOLVER = "external_sampling_mccfr"


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
		"solver": SUPPORTED_SOLVER,
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
	validate_strategy_export(payload)

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


def information_set_key(serialized_information_set):
	return json.dumps(
		serialized_information_set,
		sort_keys=True,
		separators=(",", ":"),
	)


def validate_strategy_export(payload):
	if not isinstance(payload, dict):
		raise ValueError("strategy export must be a JSON object")

	if payload.get("format_version") != STRATEGY_EXPORT_VERSION:
		raise ValueError("unsupported strategy export format_version")

	if payload.get("solver") != SUPPORTED_SOLVER:
		raise ValueError("unsupported strategy export solver")

	iterations = payload.get("iterations")
	if not isinstance(iterations, int) or iterations <= 0:
		raise ValueError("strategy export iterations must be positive")

	seed = payload.get("seed")
	if not isinstance(seed, int):
		raise ValueError("strategy export seed must be an integer")

	benchmark = payload.get("benchmark")
	if not isinstance(benchmark, dict):
		raise ValueError("strategy export benchmark metadata is required")

	starting_stacks = benchmark.get("starting_stacks")
	if (
		not isinstance(starting_stacks, list)
		or len(starting_stacks) != 2
		or any(
			not isinstance(stack, int) or stack <= 0
			for stack in starting_stacks
		)
	):
		raise ValueError(
			"strategy export starting_stacks must contain two positive integers"
		)

	for blind_name in ("small_blind", "big_blind"):
		blind = benchmark.get(blind_name)
		if not isinstance(blind, int) or blind <= 0:
			raise ValueError(
				f"strategy export {blind_name} must be positive"
		)

	action_abstraction = payload.get("action_abstraction")
	if not isinstance(action_abstraction, dict):
		raise ValueError(
			"strategy export action_abstraction metadata is required"
		)

	entries = payload.get("average_strategy")
	if not isinstance(entries, list):
		raise ValueError("strategy export average_strategy must be a list")

	if payload.get("information_set_count") != len(entries):
		raise ValueError("strategy export information_set_count mismatch")

	seen = set()

	for entry in entries:
		if not isinstance(entry, dict):
			raise ValueError("strategy export entry must be an object")

		information_set = entry.get("information_set")
		_validate_serialized_information_set(information_set)
		key = information_set_key(information_set)
		if key in seen:
			raise ValueError("duplicate strategy export information_set")
		seen.add(key)

		strategy = entry.get("strategy")
		_validate_strategy(strategy)

	return payload


def load_strategy_export(path):
	payload = json.loads(
		Path(path).read_text(encoding="utf-8")
	)
	return validate_strategy_export(payload)


class StrategyLookup:
	def __init__(self, payload):
		validate_strategy_export(payload)
		self.payload = payload
		self._strategies = {
			information_set_key(entry["information_set"]): dict(
				entry["strategy"]
			)
			for entry in payload["average_strategy"]
		}

	def lookup(self, information_set):
		key = information_set_key(
			serialize_information_set(information_set)
		)
		strategy = self._strategies.get(key)
		return dict(strategy) if strategy is not None else None


def _validate_serialized_information_set(information_set):
	if not isinstance(information_set, dict):
		raise ValueError("strategy export information_set must be an object")

	required = {
		"player",
		"hole_cards",
		"street",
		"public_board",
		"history",
		"commitments",
		"starting_stacks",
	}
	if set(information_set) != required:
		raise ValueError("strategy export information_set fields mismatch")

	if information_set["player"] not in (0, 1):
		raise ValueError("strategy export player must be 0 or 1")

	if information_set["street"] not in {
		"preflop",
		"flop",
		"turn",
		"river",
	}:
		raise ValueError("strategy export street is invalid")

	_validate_card_list(
		information_set["hole_cards"],
		"hole_cards",
		expected_length=2,
	)
	_validate_card_list(
		information_set["public_board"],
		"public_board",
	)

	if not isinstance(information_set["history"], list):
		raise ValueError("strategy export history must be a list")
	if any(
		not isinstance(action, str) or not action
		for action in information_set["history"]
	):
		raise ValueError(
			"strategy export history actions must be non-empty strings"
		)

	for field in ("commitments", "starting_stacks"):
		values = information_set[field]
		if (
			not isinstance(values, list)
			or len(values) != 2
			or any(
				not isinstance(value, int) or value < 0
				for value in values
			)
		):
			raise ValueError(
				f"strategy export {field} must contain two non-negative integers"
		)


def _validate_card_list(cards, field, expected_length=None):
	if not isinstance(cards, list):
		raise ValueError(f"strategy export {field} must be a list")
	if expected_length is not None and len(cards) != expected_length:
		raise ValueError(
			f"strategy export {field} must contain {expected_length} cards"
		)

	for card in cards:
		if (
			not isinstance(card, dict)
			or set(card) != {"rank", "suit"}
			or not isinstance(card["rank"], int)
			or card["rank"] < 2
			or card["rank"] > 14
			or card["suit"] not in {"C", "D", "H", "S"}
		):
			raise ValueError(
				f"strategy export {field} contains an invalid card"
		)


def _validate_strategy(strategy):
	if not isinstance(strategy, dict) or not strategy:
		raise ValueError("strategy export strategy must be a non-empty object")

	for action, probability in strategy.items():
		if not isinstance(action, str) or not action:
			raise ValueError(
				"strategy export action names must be non-empty strings"
		)
		if (
			not isinstance(probability, (int, float))
			or isinstance(probability, bool)
			or probability < 0.0
			or probability > 1.0
		):
			raise ValueError(
				"strategy export probabilities must be between 0 and 1"
		)

	if abs(sum(strategy.values()) - 1.0) > 1e-9:
		raise ValueError(
			"strategy export probabilities must sum to 1"
		)
