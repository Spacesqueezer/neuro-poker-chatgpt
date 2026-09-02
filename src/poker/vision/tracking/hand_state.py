from poker.vision.tracking.card_state import (
	CardStateTracker,
)


class HandStateTracker:
	"""
	Монотонное состояние текущей руки.

	Detector geometry может мигать каждый кадр. Poker hand — нет:
	preflop -> flop -> turn -> river.

	Board очищается только после серии реальных кадров без board boxes.
	"""

	def __init__(
		self,
		board_clear_scans=7,
	):
		self.cards = (
			CardStateTracker()
		)

		self.board_clear_scans = (
			board_clear_scans
		)

		self.board_missing_scans = 0
		self.hero_missing_scans = 0
		self.hand_index = 0

	def observe_geometry(
		self,
		board_count,
		hero_count,
	):
		if board_count > 0:
			self.board_missing_scans = 0
		else:
			self.board_missing_scans += 1

		if hero_count > 0:
			self.hero_missing_scans = 0
		else:
			self.hero_missing_scans += 1

		# Если board уже был и достаточно долго действительно исчез,
		# предыдущая раздача закончилась.
		if (
			self.cards.board_values
			and self.board_missing_scans
			>= self.board_clear_scans
		):
			self.cards.clear_board_for_new_hand()

			self.hand_index += 1
			self.board_missing_scans = 0

	def update_board(
		self,
		values,
	):
		return self.cards.update_board(
			values
		)

	def update_hero(
		self,
		values,
	):
		return self.cards.update_hero(
			values
		)

	@property
	def board_values(self):
		return list(
			self.cards.board_values
		)

	@property
	def hero_values(self):
		return list(
			self.cards.hero_values
		)

	@property
	def street_name(self):
		count = len(
			self.cards.board_values
		)

		if count == 0:
			return "preflop"

		if count == 3:
			return "flop"

		if count == 4:
			return "turn"

		if count == 5:
			return "river"

		return "unknown"

	def reset_geometry_only(self):
		# Resize/re-lock не является новой poker hand.
		self.board_missing_scans = 0
		self.hero_missing_scans = 0

	def reset_all(self):
		self.cards.reset_all()

		self.board_missing_scans = 0
		self.hero_missing_scans = 0
		self.hand_index = 0
