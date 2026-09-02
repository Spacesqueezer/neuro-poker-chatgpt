from collections import Counter, deque


class CardStateTracker:
	def __init__(
		self,
		history_size=5,
	):
		self.history_size = history_size
		self._board = []
		self._hero = []
		self.board_values = []
		self.hero_values = []

	def update_board(
		self,
		values,
	):
		self._ensure_slots(
			self._board,
			len(values),
		)

		for index, value in enumerate(values):
			self._board[index].append(
				value
			)

		self.board_values = [
			self._stable_value(history)
			for history in self._board
		]

		return self.board_values

	def update_hero(
		self,
		values,
	):
		self._ensure_slots(
			self._hero,
			len(values),
		)

		for index, value in enumerate(values):
			self._hero[index].append(
				value
			)

		self.hero_values = [
			self._stable_value(history)
			for history in self._hero
		]

		return self.hero_values

	def reset_board(self):
		self._board = []
		self.board_values = []

	def reset_hero(self):
		self._hero = []
		self.hero_values = []

	def _ensure_slots(
		self,
		storage,
		count,
	):
		if len(storage) != count:
			storage[:] = [
				deque(
					maxlen=self.history_size
				)
				for _ in range(count)
			]

	def _stable_value(
		self,
		history,
	):
		valid = [
			value
			for value in history
			if value
			and value != "??"
			and "?" not in value
		]

		if valid:
			return Counter(
				valid
			).most_common(1)[0][0]

		if history:
			return history[-1]

		return "??"
