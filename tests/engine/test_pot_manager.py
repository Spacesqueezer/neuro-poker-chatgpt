from poker.evaluation.evaluation_result import EvaluationResult
from poker.evaluation.hand_rank import HandRank
from poker.game.pot_manager import PotManager
from poker.player.player import Player


def result(rank, *tiebreaker):
	return EvaluationResult(rank=rank, cards=(), tiebreaker=tuple(tiebreaker))


def test_build_layers_supports_cascade_of_side_pots():
	players = [
		Player("Alice", 0),
		Player("Bob", 0),
		Player("Carol", 0),
		Player("Dave", 0),
	]
	for player, contribution in zip(players, (20, 40, 80, 160), strict=True):
		player.total_contribution = contribution

	layers = PotManager().build_layers(players)

	assert [(amount, [player.name for player in contributors]) for amount, contributors in layers] == [
		(80, ["Alice", "Bob", "Carol", "Dave"]),
		(60, ["Bob", "Carol", "Dave"]),
		(80, ["Carol", "Dave"]),
		(80, ["Dave"]),
	]


def test_settle_cascade_awards_each_layer_and_refunds_unmatched_tail():
	alice = Player("Alice", 0)
	bob = Player("Bob", 0)
	carol = Player("Carol", 0)
	dave = Player("Dave", 0)
	players = [alice, bob, carol, dave]
	for player, contribution in zip(players, (20, 40, 80, 160), strict=True):
		player.total_contribution = contribution

	results = {
		alice: result(HandRank.FOUR_OF_A_KIND, 14),
		bob: result(HandRank.FULL_HOUSE, 13),
		carol: result(HandRank.FLUSH, 12),
		dave: result(HandRank.STRAIGHT, 11),
	}

	settlement = PotManager().settle(players, 0, results)

	assert [player.chips for player in players] == [80, 60, 80, 80]
	assert settlement.refunds == {dave: 80}
	assert settlement.winners == (alice, bob, carol)
	assert [(layer.kind, layer.amount) for layer in settlement.layers] == [
		("pot", 80),
		("pot", 60),
		("pot", 80),
		("refund", 80),
	]


def test_folded_contributor_funds_layers_but_cannot_win_them():
	alice = Player("Alice", 0)
	bob = Player("Bob", 0)
	carol = Player("Carol", 0)
	players = [alice, bob, carol]
	for player, contribution in zip(players, (20, 50, 50), strict=True):
		player.total_contribution = contribution
	bob.fold()

	results = {
		alice: result(HandRank.THREE_OF_A_KIND, 14),
		carol: result(HandRank.PAIR, 12),
	}

	settlement = PotManager().settle(players, 0, results)

	assert alice.chips == 60
	assert bob.chips == 0
	assert carol.chips == 60
	assert [layer.amount for layer in settlement.layers] == [60, 60]
	assert [player.name for player in settlement.layers[1].eligible_players] == ["Carol"]


def test_side_pot_can_split_between_subset_of_players():
	alice = Player("Alice", 0)
	bob = Player("Bob", 0)
	carol = Player("Carol", 0)
	players = [alice, bob, carol]
	for player, contribution in zip(players, (20, 50, 50), strict=True):
		player.total_contribution = contribution

	results = {
		alice: result(HandRank.FOUR_OF_A_KIND, 14),
		bob: result(HandRank.PAIR, 10),
		carol: result(HandRank.PAIR, 10),
	}

	settlement = PotManager().settle(players, 0, results)

	assert alice.chips == 60
	assert bob.chips == 30
	assert carol.chips == 30
	assert settlement.layers[1].winners == (bob, carol)


def test_odd_chip_in_side_pot_goes_left_of_dealer():
	alice = Player("Alice", 0)
	bob = Player("Bob", 0)
	carol = Player("Carol", 0)
	dave = Player("Dave", 0)
	players = [alice, bob, carol, dave]
	for player, contribution in zip(players, (1, 2, 2, 2), strict=True):
		player.total_contribution = contribution
	alice.fold()

	results = {
		bob: result(HandRank.PAIR, 10),
		carol: result(HandRank.PAIR, 10),
		dave: result(HandRank.HIGH_CARD, 9),
	}

	settlement = PotManager().settle(players, 0, results)

	# Main pot is 4 and splits 2/2. Side pot is 3 and splits 2/1.
	# Left of dealer Alice: Bob receives the odd chip before Carol.
	assert bob.chips == 4
	assert carol.chips == 3
	assert dave.chips == 0
	assert settlement.layers[1].amount == 3
	assert settlement.layers[1].winners == (bob, carol)
