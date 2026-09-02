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
	def detect_board(self, table_frame):
		height, width = table_frame.shape[:2]

		region = (
			int(width * 0.26),
			int(height * 0.28),
			int(width * 0.74),
			int(height * 0.62),
		)

		cards = self._detect_in_region(
			table_frame,
			region,
		)

		cards = sorted(
			cards,
			key=lambda card: card.x,
		)

		# Валидные состояния Hold'em: 0 / 3 / 4 / 5 карт.
		if len(cards) > 5:
			cards = cards[:5]

		if len(cards) in (1, 2):
			return []

		return cards

	def detect_hero(
		self,
		table_frame,
		hero_panel,
	):
		if hero_panel is None:
			return []

		height, width = table_frame.shape[:2]

		panel_center = np.array(
			hero_panel.center,
			dtype=np.float32,
		)

		# PokerDom рисует hole cards непосредственно НАД name/panel.
		# Для верхнего seat это означает "наружу" от центра стола,
		# поэтому старая логика "ищи только по направлению к центру"
		# систематически пропускала HERO сверху.
		#
		# Ищем компактную область вокруг/над panel — это работает
		# для верхних, нижних и боковых мест.
		search_width = int(
			max(
				hero_panel.width * 2.6,
				width * 0.18,
			)
		)

		search_height = int(
			max(
				hero_panel.height * 4.2,
				height * 0.24,
			)
		)

		x1 = int(
			panel_center[0]
			- search_width / 2
		)

		y1 = int(
			hero_panel.y
			- search_height * 0.82
		)

		x2 = x1 + search_width

		y2 = int(
			hero_panel.y
			+ hero_panel.height
			+ search_height * 0.18
		)

		region = (
			max(0, x1),
			max(0, y1),
			min(width, x2),
			min(height, y2),
		)

		cards = self._detect_in_region(
			table_frame,
			region,
		)

		if len(cards) > 2:
			cards = self._pick_nearest_pair(
				cards,
				panel_center,
			)

		return sorted(
			cards[:2],
			key=lambda card: card.x,
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

		mask = cv2.morphologyEx(
			mask,
			cv2.MORPH_CLOSE,
			cv2.getStructuringElement(
				cv2.MORPH_RECT,
				(5, 7),
			),
			iterations=2,
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
