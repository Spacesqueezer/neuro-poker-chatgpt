from collections import Counter, deque


UNKNOWN_CARD = "??"


def _valid_card(
	value,
):
	return bool(
		value
		and value != UNKNOWN_CARD
		and "?" not in value
		and len(value) == 2
	)


class _CardSlot:
	def __init__(
		self,
		history_size=9,
		switch_votes=3,
	):
		self.history = deque(
			maxlen=history_size
		)

		self.confirmed = None
		self.switch_votes = (
			switch_votes
		)

	def update(
		self,
		value,
	):
		if not _valid_card(
			value
		):
			return self.value()

		self.history.append(
			value
		)

		if self.confirmed is None:
			# Первый валидный read можно показать сразу.
			# Дальнейшие изменения уже требуют голосования.
			self.confirmed = value

			return self.confirmed

		if value == self.confirmed:
			return self.confirmed

		counts = Counter(
			self.history
		)

		challenger, votes = (
			counts.most_common(1)[0]
		)

		if (
			challenger
			!= self.confirmed
			and votes
			>= self.switch_votes
			and votes
			> counts.get(
				self.confirmed,
				0,
			)
		):
			self.confirmed = (
				challenger
			)

			# После реальной смены начинаем свежую историю.
			self.history.clear()
			self.history.append(
				challenger
			)

		return self.confirmed

	def value(self):
		return (
			self.confirmed
			or UNKNOWN_CARD
		)

	def clear_votes(self):
		self.history.clear()

	def reset(self):
		self.history.clear()
		self.confirmed = None


class CardStateTracker:
	"""
	Устойчивые значения board / hero cards.

	Главное отличие от старого tracker:
	- изменение количества detector boxes больше не уничтожает всю историю;
	- краткий `5h -> Jh -> 5h` не меняет confirmed card;
	- пропавшая карта не сдвигает индексы уже подтверждённого board.
	"""

	def __init__(
		self,
		history_size=9,
		board_switch_votes=3,
		hero_switch_votes=4,
	):
		self.history_size = (
			history_size
		)

		self.board_switch_votes = (
			board_switch_votes
		)

		self.hero_switch_votes = (
			hero_switch_votes
		)

		self._board = []

		self._hero = [
			_CardSlot(
				history_size=history_size,
				switch_votes=hero_switch_votes,
			),
			_CardSlot(
				history_size=history_size,
				switch_votes=hero_switch_votes,
			),
		]

		self.board_values = []
		self.hero_values = []

	def update_board(
		self,
		values,
	):
		values = list(
			values
			or []
		)

		count = len(values)

		# В Hold'em board появляется только 3 -> 4 -> 5.
		# 1/2 карты здесь означают detector miss.
		if count not in (
			3,
			4,
			5,
		):
			return list(
				self.board_values
			)

		# Если мы уже подтвердили больше slots, более короткий read
		# игнорируем целиком. Иначе пропуск средней карты сдвинет все
		# последующие значения на один индекс.
		if (
			self._board
			and count
			< len(
				self._board
			)
		):
			return list(
				self.board_values
			)

		while len(
			self._board
		) < count:
			self._board.append(
				_CardSlot(
					history_size=(
						self.history_size
					),
					switch_votes=(
						self.board_switch_votes
					),
				)
			)

		for index, value in enumerate(
			values
		):
			self._board[
				index
			].update(
				value
			)

		self.board_values = [
			slot.value()
			for slot in self._board
		]

		return list(
			self.board_values
		)

	def update_hero(
		self,
		values,
	):
		values = list(
			values
			or []
		)

		if len(values) != 2:
			return list(
				self.hero_values
			)

		for index, value in enumerate(
			values
		):
			self._hero[
				index
			].update(
				value
			)

		self.hero_values = [
			slot.value()
			for slot in self._hero
		]

		return list(
			self.hero_values
		)

	def clear_board_for_new_hand(
		self,
	):
		self._board = []
		self.board_values = []

		# Новый hand разрешает новым hole cards быстрее вытеснить
		# старую пару, но старые значения держим до появления новых,
		# чтобы короткий transition не давал мигания.
		for slot in self._hero:
			slot.clear_votes()

	def reset_board(self):
		self._board = []
		self.board_values = []

	def reset_hero(self):
		for slot in self._hero:
			slot.reset()

		self.hero_values = []

	def reset_all(self):
		self.reset_board()
		self.reset_hero()
