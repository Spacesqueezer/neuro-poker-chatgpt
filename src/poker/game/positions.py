POSITION_LABELS = {
	2: ("BTN/SB", "BB"),
	3: ("BTN", "SB", "BB"),
	4: ("BTN", "SB", "BB", "CO"),
	5: ("BTN", "SB", "BB", "UTG", "CO"),
	6: ("BTN", "SB", "BB", "UTG", "HJ", "CO"),
	7: ("BTN", "SB", "BB", "UTG", "MP", "HJ", "CO"),
	8: ("BTN", "SB", "BB", "UTG", "UTG+1", "MP", "HJ", "CO"),
	9: ("BTN", "SB", "BB", "UTG", "UTG+1", "MP", "LJ", "HJ", "CO"),
}


def position_labels(player_count):
	if player_count not in POSITION_LABELS:
		raise ValueError(
			f"Unsupported table size for canonical positions: {player_count}"
		)

	return POSITION_LABELS[player_count]


def positions_by_player(players, dealer_index):
	labels = position_labels(len(players))
	result = {}

	for offset, label in enumerate(labels):
		player = players[(dealer_index + offset) % len(players)]
		result[player.name] = label

	return result
