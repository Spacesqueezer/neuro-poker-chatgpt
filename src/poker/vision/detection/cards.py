from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class CardBox:
	x: int
	y: int
	width: int
	height: int

	@property
	def rect(self):
		return (
			self.x,
			self.y,
			self.x + self.width,
			self.y + self.height,
		)

	@property
	def center(self):
		return (
			self.x + self.width / 2,
			self.y + self.height / 2,
		)


class CardDetector:
	def __init__(self):
		self.card_size_hint = None

	def detect_board(
		self,
		table_frame,
	):
		height, width = (
			table_frame.shape[:2]
		)

		region = (
			int(width * 0.26),
			int(height * 0.28),
			int(width * 0.74),
			int(height * 0.62),
		)

		# Сначала обычный строгий detector.
		cards = self._detect_in_region(
			table_frame,
			region,
		)

		if cards:
			self._remember_card_size(
				cards
			)

		# Фишки иногда закрывают низ board card. Тогда белый contour
		# становится короче и строгий detector может её потерять.
		#
		# Второй проход разрешает частично видимую карту и восстанавливает
		# полный CardBox по известному/оценённому размеру карты.
		partial_cards = (
			self._detect_partial_in_region(
				table_frame,
				region,
			)
		)

		cards = self._merge_cards(
			cards,
			partial_cards,
		)

		cards = sorted(
			cards,
			key=lambda card: card.x,
		)

		if len(cards) > 5:
			cards = cards[:5]

		# Валидные состояния Hold'em: 0 / 3 / 4 / 5 карт.
		if len(cards) in (
			1,
			2,
		):
			return []

		if cards:
			self._remember_card_size(
				cards
			)

		return cards


	def detect_hero(
		self,
		table_frame,
		hero_panel,
	):
		"""
		HERO cards используют тот же detector, что и board.

		Дополнительно разрешаем partial-card fallback, потому что PokerDom
		часто закрывает нижнюю часть открытой карты player panel.
		"""
		if hero_panel is None:
			return []

		height, width = (
			table_frame.shape[:2]
		)

		panel_center_x = float(
			hero_panel.center[0]
		)

		expected_width, expected_height = (
			self._expected_card_size(
				table_frame
			)
		)

		pair_width = (
			expected_width * 2
			+ max(
				3,
				int(
					round(
						width * 0.0035
					)
				),
			)
		)

		search_width = int(
			round(
				max(
					pair_width * 1.28,
					hero_panel.width * 1.35,
				)
			)
		)

		search_height = int(
			round(
				expected_height * 1.20
			)
		)

		search_width = min(
			search_width,
			int(
				width * 0.19
			),
		)

		search_height = min(
			search_height,
			int(
				height * 0.24
			),
		)

		x1 = int(
			round(
				panel_center_x
				- search_width / 2
			)
		)

		# Нижние 10-20% карт могут быть перекрыты player panel.
		# Поэтому ROI чуть заходит внутрь panel.
		y2 = int(
			round(
				hero_panel.y
				+ hero_panel.height * 0.28
			)
		)

		y1 = int(
			round(
				y2
				- search_height
			)
		)

		region = (
			max(0, x1),
			max(0, y1),
			min(
				width,
				x1 + search_width,
			),
			min(
				height,
				y2,
			),
		)

		full_cards = self._detect_in_region(
			table_frame,
			region,
		)

		partial_cards = (
			self._detect_partial_in_region(
				table_frame,
				region,
			)
		)

		cards = self._merge_cards(
			full_cards,
			partial_cards,
		)

		if len(cards) < 2:
			return []

		# Hole cards должны быть рядом с HERO и примерно на одной линии.
		expected_center = (
			panel_center_x,
			float(
				hero_panel.y
				- expected_height * 0.48
			),
		)

		cards = sorted(
			cards,
			key=lambda card: np.hypot(
				card.center[0]
				- expected_center[0],
				card.center[1]
				- expected_center[1],
			),
		)

		best = sorted(
			cards[:2],
			key=lambda card: card.x,
		)

		if len(best) == 2:
			y_delta = abs(
				best[0].y
				- best[1].y
			)

			if (
				y_delta
				> expected_height * 0.22
			):
				return []

			pair_gap = (
				best[1].x
				- (
					best[0].x
					+ best[0].width
				)
			)

			if (
				pair_gap
				> expected_width * 0.35
			):
				return []

		return best


	def signature(
		self,
		cards,
	):
		"""
		Стабильная геометрическая сигнатура набора карт.

		runner использует её, чтобы понять: изменилась ли раскладка карт
		и нужно ли сбрасывать накопленный CardStateTracker.
		"""
		if not cards:
			return ()

		return tuple(
			(
				int(card.x),
				int(card.y),
				int(card.width),
				int(card.height),
			)
			for card in sorted(
				cards,
				key=lambda item: (
					item.x,
					item.y,
				),
			)
		)

	def _detect_in_region(
		self,
		frame,
		region,
	):
		x1, y1, x2, y2 = region

		crop = frame[
			y1:y2,
			x1:x2,
		]

		if crop.size == 0:
			return []

		hsv = cv2.cvtColor(
			crop,
			cv2.COLOR_BGR2HSV,
		)

		# Лицевая сторона карт PokerDom почти белая/светло-серая.
		mask = cv2.inRange(
			hsv,
			np.array([0, 0, 135], dtype=np.uint8),
			np.array([179, 105, 255], dtype=np.uint8),
		)

		# Карты PokerDom стоят с промежутком всего в несколько пикселей.
		# Старый CLOSE (5x7) x2 мог физически склеить две соседние карты
		# в один contour. Нужна только лёгкая чистка внутри одной карты.
		mask = cv2.morphologyEx(
			mask,
			cv2.MORPH_CLOSE,
			cv2.getStructuringElement(
				cv2.MORPH_RECT,
				(3, 3),
			),
			iterations=1,
		)

		contours, _ = cv2.findContours(
			mask,
			cv2.RETR_EXTERNAL,
			cv2.CHAIN_APPROX_SIMPLE,
		)

		frame_height, frame_width = frame.shape[:2]
		result = []

		for contour in contours:
			x, y, width, height = cv2.boundingRect(
				contour
			)

			absolute_x = x1 + x
			absolute_y = y1 + y

			rel_width = width / frame_width
			rel_height = height / frame_height
			aspect = width / max(height, 1)

			if not 0.035 <= rel_width <= 0.10:
				continue

			if not 0.075 <= rel_height <= 0.19:
				continue

			if not 0.48 <= aspect <= 0.85:
				continue

			area = cv2.contourArea(
				contour
			)

			box_area = width * height

			if box_area <= 0:
				continue

			fill_ratio = area / box_area

			if fill_ratio < 0.62:
				continue

			result.append(
				CardBox(
					x=absolute_x,
					y=absolute_y,
					width=width,
					height=height,
				)
			)

		return self._deduplicate(
			result
		)

	def _detect_partial_in_region(
		self,
		frame,
		region,
	):
		"""
		Находит частично перекрытые карты.

		Ключевая идея: rank/suit находятся в верхней части карты, поэтому
		для recognition нам не обязательно видеть весь белый прямоугольник.

		Если нижнюю часть закрыл player panel или стопка фишек, берём
		видимый верх карты и восстанавливаем полный CardBox ожидаемого размера.
		"""
		x1, y1, x2, y2 = region

		crop = frame[
			y1:y2,
			x1:x2,
		]

		if crop.size == 0:
			return []

		hsv = cv2.cvtColor(
			crop,
			cv2.COLOR_BGR2HSV,
		)

		mask = cv2.inRange(
			hsv,
			np.array(
				[0, 0, 135],
				dtype=np.uint8,
			),
			np.array(
				[179, 105, 255],
				dtype=np.uint8,
			),
		)

		mask = cv2.morphologyEx(
			mask,
			cv2.MORPH_CLOSE,
			cv2.getStructuringElement(
				cv2.MORPH_RECT,
				(3, 3),
			),
			iterations=1,
		)

		contours, _ = cv2.findContours(
			mask,
			cv2.RETR_EXTERNAL,
			cv2.CHAIN_APPROX_SIMPLE,
		)

		expected_width, expected_height = (
			self._expected_card_size(
				frame
			)
		)

		frame_height, frame_width = (
			frame.shape[:2]
		)

		result = []

		for contour in contours:
			x, y, box_width, box_height = (
				cv2.boundingRect(
					contour
				)
			)

			# Ширина карты при перекрытии снизу почти не меняется.
			width_ratio = (
				box_width
				/ max(
					expected_width,
					1,
				)
			)

			# Высота может заметно уменьшиться.
			height_ratio = (
				box_height
				/ max(
					expected_height,
					1,
				)
			)

			if not (
				0.72
				<= width_ratio
				<= 1.18
			):
				continue

			if not (
				0.42
				<= height_ratio
				<= 1.08
			):
				continue

			area = cv2.contourArea(
				contour
			)

			box_area = (
				box_width
				* box_height
			)

			if box_area <= 0:
				continue

			fill_ratio = (
				area
				/ box_area
			)

			# Для частично закрытой карты contour может быть рваным.
			if fill_ratio < 0.48:
				continue

			absolute_x = (
				x1 + x
			)

			absolute_y = (
				y1 + y
			)

			# Восстанавливаем канонический размер от видимого top-left.
			# Нижняя часть может попасть под overlay — это нормально:
			# rank/suit extractor всё равно работает в верхнем левом углу.
			card_width = min(
				expected_width,
				frame_width
				- absolute_x,
			)

			card_height = min(
				expected_height,
				frame_height
				- absolute_y,
			)

			if (
				card_width <= 8
				or card_height <= 16
			):
				continue

			result.append(
				CardBox(
					x=absolute_x,
					y=absolute_y,
					width=card_width,
					height=card_height,
				)
			)

		return self._deduplicate(
			result
		)

	def _expected_card_size(
		self,
		frame,
	):
		if self.card_size_hint is not None:
			return self.card_size_hint

		height, width = (
			frame.shape[:2]
		)

		# Хорошая оценка для PokerDom при любом resize:
		# высота карты ~11-12% table crop.
		card_height = max(
			36,
			int(
				round(
					height * 0.115
				)
			),
		)

		card_width = max(
			22,
			int(
				round(
					card_height * 0.70
				)
			),
		)

		return (
			card_width,
			card_height,
		)

	def _remember_card_size(
		self,
		cards,
	):
		if not cards:
			return

		widths = [
			card.width
			for card in cards
			if card.width > 0
		]

		heights = [
			card.height
			for card in cards
			if card.height > 0
		]

		if (
			not widths
			or not heights
		):
			return

		width = int(
			round(
				float(
					np.median(
						widths
					)
				)
			)
		)

		height = int(
			round(
				float(
					np.median(
						heights
					)
				)
			)
		)

		if (
			width <= 8
			or height <= 16
		):
			return

		if self.card_size_hint is None:
			self.card_size_hint = (
				width,
				height,
			)
			return

		old_width, old_height = (
			self.card_size_hint
		)

		# Плавно обновляем hint, чтобы один кривой contour его не испортил.
		self.card_size_hint = (
			int(
				round(
					old_width * 0.75
					+ width * 0.25
				)
			),
			int(
				round(
					old_height * 0.75
					+ height * 0.25
				)
			),
		)

	def _merge_cards(
		self,
		primary,
		secondary,
	):
		result = list(
			primary
		)

		for card in secondary:
			duplicate = False

			for existing in result:
				distance = float(
					np.hypot(
						card.center[0]
						- existing.center[0],
						card.center[1]
						- existing.center[1],
					)
				)

				if (
					distance
					< max(
						card.width,
						existing.width,
					) * 0.55
				):
					duplicate = True
					break

			if not duplicate:
				result.append(
					card
				)

		return self._deduplicate(
			result
		)


	def _deduplicate(
		self,
		cards,
	):
		result = []

		for card in sorted(
			cards,
			key=lambda item: item.width * item.height,
			reverse=True,
		):
			duplicate = False

			for existing in result:
				distance = np.hypot(
					card.center[0] - existing.center[0],
					card.center[1] - existing.center[1],
				)

				if distance < max(
					card.width,
					existing.width,
				) * 0.55:
					duplicate = True
					break

			if not duplicate:
				result.append(card)

		return result

	def _pick_nearest_pair(
		self,
		cards,
		panel_center,
	):
		return sorted(
			cards,
			key=lambda card: np.hypot(
				card.center[0] - panel_center[0],
				card.center[1] - panel_center[1],
			),
		)[:2]


def crop_card(
	frame,
	card,
):
	x1, y1, x2, y2 = card.rect

	return frame[
		y1:y2,
		x1:x2,
	]
