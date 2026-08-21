from poker.players.profile import PlayerProfile

STYLE_PRESETS = {
	"nit": (0.16, 0.12, 0.3, 0.05),
	"tag": (0.24, 0.20, 0.6, 0.12),
	"lag": (0.38, 0.32, 0.9, 0.25),
	"maniac": (0.65, 0.45, 1.4, 0.45),
	"fish": (0.45, 0.10, 0.2, 0.05),
	"calling_station": (0.55, 0.08, 0.1, 0.02),
}


def generate_player_pool():
	profiles = []
	index = 1

	for style, values in STYLE_PRESETS.items():
		count = 10 if style != "tag" else 20

		for _ in range(count):
			profiles.append(
				PlayerProfile(
					name=f"Player_{index:03d}",
					style=style,
					vpip_target=values[0],
					pfr_target=values[1],
					aggression=values[2],
					bluff_frequency=values[3],
				)
			)
			index += 1

	return profiles
