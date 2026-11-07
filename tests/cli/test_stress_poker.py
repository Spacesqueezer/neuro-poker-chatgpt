import random

from tools.stress_poker import run_hand


def test_random_smoke_hand_completes_with_invariants():
	history = run_hand(seed=7001, rng=random.Random(7001))

	assert history.result in {"showdown", "complete"}
	assert sum(history.final_stacks.values()) == 300
