from poker.learning.import_teacher import TeacherRecordImporter

def test_teacher_record_importer_maps_fields_to_learning_sample():
	record = {
		"information_set": {
			"player": 0,
			"street": "flop",
			"hole_cards": [{"rank": 14, "suit": "S"}, {"rank": 13, "suit": "S"}],
			"public_board": [{"rank": 2, "suit": "C"}, {"rank": 3, "suit": "C"}, {"rank": 4, "suit": "C"}],
			"commitments": [5, 4],
			"starting_stacks": [20, 20],
			"history": ["call", "check", "check"],
		},
		"legal_actions": ["check", "fold", "bet_1bb"],
		"strategy": {
			"check": 0.2,
			"fold": 0.1,
			"bet_1bb": 0.7,
		}
	}

	importer = TeacherRecordImporter(small_blind=1, big_blind=2)
	sample = importer.import_record(record)

	assert sample.acting_player == "player_0"
	# bet_1bb is maximum probability (0.7), so it should be mapped to BET
	# Action index for BET in LearningActionEncoder is 3 (FOLD, CHECK, CALL, BET, RAISE, ALL_IN)
	assert sample.action_index == 3

def test_teacher_record_importer_handles_ties_deterministically():
	record = {
		"information_set": {
			"player": 1,
			"street": "preflop",
			"hole_cards": [{"rank": 14, "suit": "S"}, {"rank": 13, "suit": "S"}],
			"public_board": [],
			"commitments": [1, 2],
			"starting_stacks": [20, 20],
			"history": [],
		},
		"legal_actions": ["fold", "call", "raise", "shove"],
		"strategy": {
			"fold": 0.5,
			"call": 0.5,
		}
	}

	# Deterministic tie-breaking prefers the action that appears earlier in the dictionary keys, which is 'fold' here
	importer = TeacherRecordImporter(small_blind=1, big_blind=2)
	sample = importer.import_record(record)

	assert sample.acting_player == "player_1"
	# 'fold' is index 0
	assert sample.action_index == 0
