from poker.arena.stats import ArenaStats


def test_arena_summary_contains_bb_per_100():
	stats = ArenaStats()
	stats.hands = 100
	stats.update_players({"alice": 120, "bob": 80}, 100)

	summary = stats.summary()

	assert summary["bb_per_100"]["alice"] == 10
	assert summary["bb_per_100"]["bob"] == -10
