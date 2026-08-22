def find_hero(players, hero_name):
	for player in players:
		if player.get("name", "").lower() == hero_name.lower():
			return player
	return None
