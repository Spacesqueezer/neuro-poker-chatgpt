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


@dataclass
class _BoardGeometry:
	x: float
	y: float
	width: float
	height: float
	pitch: float
	count: int


class CardDetector:
	"""
	Полностью новый detector карт PokerDom.

	Главная идея:
	карта — это не "идеальный белый contour".
	Нижнюю часть могут закрыть chips/player panel, отдельный contour может
	временно пропасть, но геометрия раскладки карт остаётся стабильной.

	Board:
		1) на flop находим реальную горизонтальную тройку;
		2) фиксируем canonical card size + pitch;
		3) turn/river определяем по новым slot positions;
		4) если середина временно потерялась, возвращаем canonical box
		   на её месте, а не сдвигаем все последующие карты.

	HERO:
		1) размер карты берём из board geometry или table scale;
		2) строим две ожидаемые соседние карты непосредственно над hero panel;
		3) локально уточняем положение каждой по светлой верхней части;
		4) нижняя часть карты может быть полностью перекрыта UI.
	"""

	def __init__(
		self,
	):
		self.board_geometry = None
		self.card_size_hint = None
		self.board_empty_scans = 0

		self.board_reset_scans = 6

		self.white_low = np.array(
			[0, 0, 140],
			dtype=np.uint8,
		)

		self.white_high = np.array(
			[179, 105, 255],
			dtype=np.uint8,
		)

	def detect_board(
		self,
		table_frame,
	):
		if (
			table_frame is None
			or table_frame.size == 0
		):
			return []

		height, width = (
			table_frame.shape[:2]
		)

		region = (
			int(width * 0.22),
			int(height * 0.24),
			int(width * 0.78),
			int(height * 0.64),
		)

		mask = self._white_mask(
			table_frame,
			region,
		)

		if mask is None:
			return []

		if self.board_geometry is None:
			candidates = (
				self._find_candidates(
					table_frame,
					region,
					expected_size=None,
				)
			)

			geometry = (
				self._fit_new_board(
					table_frame,
					candidates,
				)
			)

			if geometry is None:
				self._note_board_empty()
				return []

			self.board_geometry = (
				geometry
			)

			self.card_size_hint = (
				int(
					round(
						geometry.width
					)
				),
				int(
					round(
						geometry.height
					)
				),
			)

			self.board_empty_scans = 0

			return self._board_boxes(
				table_frame
			)

		self._update_board_geometry(
			table_frame,
			region,
		)

		if not self._board_present(
			table_frame
		):
			self._note_board_empty()

			if self.board_geometry is None:
				return []
		else:
			self.board_empty_scans = 0

		return self._board_boxes(
			table_frame
		)

	def detect_hero(
		self,
		table_frame,
		hero_panel,
	):
		if (
			hero_panel is None
			or table_frame is None
			or table_frame.size == 0
		):
			return []

		height, width = (
			table_frame.shape[:2]
		)

		card_width, card_height = (
			self._expected_card_size(
				table_frame
			)
		)

		gap = max(
			3,
			int(
				round(
					card_width * 0.055
				)
			),
		)

		pair_width = (
			card_width * 2
			+ gap
		)

		center_x = float(
			hero_panel.center[0]
		)

		# Реальные PokerDom hole cards:
		#	- стоят горизонтальной парой;
		#	- центр пары совпадает примерно с центром player panel;
		#	- низ карты заходит под верх player panel.
		base_y = int(
			round(
				hero_panel.y
				- card_height * 0.86
			)
		)

		first_x = int(
			round(
				center_x
				- pair_width / 2
			)
		)

		expected = [
			CardBox(
				x=first_x,
				y=base_y,
				width=card_width,
				height=card_height,
			),
			CardBox(
				x=(
					first_x
					+ card_width
					+ gap
				),
				y=base_y,
				width=card_width,
				height=card_height,
			),
		]

		result = []

		for box in expected:
			refined = (
				self._refine_expected_card(
					table_frame,
					box,
					search_x=max(
						4,
						int(
							round(
								card_width
								* 0.22
							)
						),
					),
					search_y=max(
						3,
						int(
							round(
								card_height
								* 0.12
							)
						),
					),
				)
			)

			evidence = (
				self._card_evidence(
					table_frame,
					refined,
					top_fraction=0.62,
				)
			)

			if evidence >= 0.16:
				result.append(
					refined
				)

		# Если одна карта слегка хуже по белой маске, но соседняя уверенно
		# найдена, геометрия пары намного надёжнее одиночного contour.
		if len(result) == 1:
			known = result[0]

			known_is_left = (
				known.center[0]
				< center_x
			)

			if known_is_left:
				other = CardBox(
					x=int(
						round(
							known.x
							+ card_width
							+ gap
						)
					),
					y=known.y,
					width=card_width,
					height=card_height,
				)
			else:
				other = CardBox(
					x=int(
						round(
							known.x
							- card_width
							- gap
						)
					),
					y=known.y,
					width=card_width,
					height=card_height,
				)

			other = self._clip_box(
				table_frame,
				other,
			)

			if (
				self._card_evidence(
					table_frame,
					other,
					top_fraction=0.50,
				)
				>= 0.09
			):
				result.append(
					other
				)

		if len(result) != 2:
			return []

		result = sorted(
			result,
			key=lambda card: card.x,
		)

		# HERO pair должна быть компактной. Никаких "рамок на полстола".
		center_distance = abs(
			(
				result[0].center[0]
				+ result[1].center[0]
			) / 2.0
			- center_x
		)

		if (
			center_distance
			> card_width * 0.45
		):
			return []

		return result

	def signature(
		self,
		cards,
	):
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

	def reset(
		self,
	):
		self.board_geometry = None
		self.card_size_hint = None
		self.board_empty_scans = 0

	def _fit_new_board(
		self,
		frame,
		candidates,
	):
		if len(candidates) < 3:
			return None

		# Ищем именно горизонтальную регулярную группу.
		best = None
		best_score = None

		for first_index in range(
			len(candidates)
		):
			for second_index in range(
				first_index + 1,
				len(candidates),
			):
				for third_index in range(
					second_index + 1,
					len(candidates),
				):
					group = sorted(
						[
							candidates[
								first_index
							],
							candidates[
								second_index
							],
							candidates[
								third_index
							],
						],
						key=lambda card: card.x,
					)

					if not self._regular_row(
						group
					):
						continue

					pitch_a = (
						group[1].center[0]
						- group[0].center[0]
					)

					pitch_b = (
						group[2].center[0]
						- group[1].center[0]
					)

					pitch = (
						pitch_a
						+ pitch_b
					) / 2.0

					widths = [
						card.width
						for card in group
					]

					heights = [
						card.height
						for card in group
					]

					card_width = float(
						np.median(
							widths
						)
					)

					card_height = float(
						np.median(
							heights
						)
					)

					center_y = float(
						np.median(
							[
								card.center[1]
								for card
								in group
							]
						)
					)

					pitch_error = abs(
						pitch_a
						- pitch_b
					)

					y_error = (
						max(
							card.center[1]
							for card
							in group
						)
						- min(
							card.center[1]
							for card
							in group
						)
					)

					size_error = (
						max(widths)
						- min(widths)
						+ max(heights)
						- min(heights)
					)

					score = (
						pitch_error * 3.0
						+ y_error * 2.0
						+ size_error
					)

					if (
						best_score is None
						or score < best_score
					):
						best_score = score
						best = (
							group,
							card_width,
							card_height,
							center_y,
							pitch,
						)

		if best is None:
			return None

		(
			group,
			card_width,
			card_height,
			center_y,
			pitch,
		) = best

		first_center_x = float(
			group[0].center[0]
		)

		geometry = _BoardGeometry(
			x=(
				first_center_x
				- card_width / 2.0
			),
			y=(
				center_y
				- card_height / 2.0
			),
			width=card_width,
			height=card_height,
			pitch=pitch,
			count=3,
		)

		# Если detector стартовал уже на turn/river, сразу проверим
		# следующие canonical slots.
		for target_count in (
			4,
			5,
		):
			test_box = self._geometry_box(
				frame,
				geometry,
				target_count - 1,
			)

			if (
				self._card_evidence(
					frame,
					test_box,
					top_fraction=0.70,
				)
				>= 0.18
			):
				geometry.count = (
					target_count
				)
			else:
				break

		return geometry

	def _update_board_geometry(
		self,
		frame,
		region,
	):
		geometry = self.board_geometry

		if geometry is None:
			return

		expected_size = (
			int(
				round(
					geometry.width
				)
			),
			int(
				round(
					geometry.height
				)
			),
		)

		candidates = (
			self._find_candidates(
				frame,
				region,
				expected_size=(
					expected_size
				),
			)
		)

		matched = []

		for candidate in candidates:
			index = int(
				round(
					(
						candidate.center[0]
						- (
							geometry.x
							+ geometry.width
							/ 2.0
						)
					)
					/ max(
						geometry.pitch,
						1.0,
					)
				)
			)

			if not (
				0
				<= index
				<= 4
			):
				continue

			expected = (
				self._geometry_box(
					frame,
					geometry,
					index,
				)
			)

			distance = float(
				np.hypot(
					candidate.center[0]
					- expected.center[0],
					candidate.center[1]
					- expected.center[1],
				)
			)

			if (
				distance
				> geometry.width * 0.55
			):
				continue

			matched.append(
				(
					index,
					candidate,
				)
			)

		if matched:
			x_offsets = []
			y_offsets = []
			widths = []
			heights = []

			for index, card in matched:
				expected_center_x = (
					geometry.x
					+ geometry.width / 2.0
					+ geometry.pitch * index
				)

				x_offsets.append(
					card.center[0]
					- expected_center_x
				)

				y_offsets.append(
					card.center[1]
					- (
						geometry.y
						+ geometry.height / 2.0
					)
				)

				widths.append(
					card.width
				)

				heights.append(
					card.height
				)

			geometry.x += (
				float(
					np.median(
						x_offsets
					)
				)
				* 0.30
			)

			geometry.y += (
				float(
					np.median(
						y_offsets
					)
				)
				* 0.30
			)

			measured_width = float(
				np.median(
					widths
				)
			)

			measured_height = float(
				np.median(
					heights
				)
			)

			geometry.width = (
				geometry.width * 0.85
				+ measured_width * 0.15
			)

			geometry.height = (
				geometry.height * 0.85
				+ measured_height * 0.15
			)

			self.card_size_hint = (
				int(
					round(
						geometry.width
					)
				),
				int(
					round(
						geometry.height
					)
				),
			)

		# Street count не определяется количеством contours.
		# Проверяем следующий slot напрямую по изображению.
		if geometry.count < 5:
			next_box = (
				self._geometry_box(
					frame,
					geometry,
					geometry.count,
				)
			)

			evidence = (
				self._card_evidence(
					frame,
					next_box,
					top_fraction=0.72,
				)
			)

			if evidence >= 0.17:
				geometry.count += 1

	def _board_present(
		self,
		frame,
	):
		geometry = self.board_geometry

		if geometry is None:
			return False

		visible = 0

		for index in range(
			min(
				geometry.count,
				3,
			)
		):
			box = self._geometry_box(
				frame,
				geometry,
				index,
			)

			if (
				self._card_evidence(
					frame,
					box,
					top_fraction=0.58,
				)
				>= 0.11
			):
				visible += 1

		return visible >= 2

	def _note_board_empty(
		self,
	):
		self.board_empty_scans += 1

		if (
			self.board_empty_scans
			>= self.board_reset_scans
		):
			self.board_geometry = None
			self.card_size_hint = None
			self.board_empty_scans = 0

	def _board_boxes(
		self,
		frame,
	):
		geometry = self.board_geometry

		if geometry is None:
			return []

		return [
			self._geometry_box(
				frame,
				geometry,
				index,
			)
			for index in range(
				geometry.count
			)
		]

	def _geometry_box(
		self,
		frame,
		geometry,
		index,
	):
		box = CardBox(
			x=int(
				round(
					geometry.x
					+ geometry.pitch
					* index
				)
			),
			y=int(
				round(
					geometry.y
				)
			),
			width=int(
				round(
					geometry.width
				)
			),
			height=int(
				round(
					geometry.height
				)
			),
		)

		return self._clip_box(
			frame,
			box,
		)

	def _find_candidates(
		self,
		frame,
		region,
		expected_size,
	):
		x1, y1, x2, y2 = region

		mask = self._white_mask(
			frame,
			region,
		)

		if mask is None:
			return []

		contours, _ = (
			cv2.findContours(
				mask,
				cv2.RETR_EXTERNAL,
				cv2.CHAIN_APPROX_SIMPLE,
			)
		)

		frame_height, frame_width = (
			frame.shape[:2]
		)

		if expected_size is None:
			expected_height = max(
				36,
				int(
					round(
						frame_height
						* 0.115
					)
				),
			)

			expected_width = max(
				22,
				int(
					round(
						expected_height
						* 0.70
					)
				),
			)
		else:
			(
				expected_width,
				expected_height,
			) = expected_size

		result = []

		for contour in contours:
			x, y, width, height = (
				cv2.boundingRect(
					contour
				)
			)

			width_ratio = (
				width
				/ max(
					expected_width,
					1,
				)
			)

			height_ratio = (
				height
				/ max(
					expected_height,
					1,
				)
			)

			# Полная карта и карта с закрытым низом проходят одним путём.
			if not (
				0.60
				<= width_ratio
				<= 1.35
			):
				continue

			if not (
				0.38
				<= height_ratio
				<= 1.28
			):
				continue

			area = cv2.contourArea(
				contour
			)

			box_area = (
				width
				* height
			)

			if box_area <= 0:
				continue

			fill_ratio = (
				area
				/ box_area
			)

			if fill_ratio < 0.42:
				continue

			absolute_x = x1 + x
			absolute_y = y1 + y

			# Частично перекрытая карта получает canonical size.
			result.append(
				CardBox(
					x=absolute_x,
					y=absolute_y,
					width=(
						expected_width
						if height_ratio < 0.82
						else width
					),
					height=(
						expected_height
						if height_ratio < 0.82
						else height
					),
				)
			)

		result.extend(
			self._split_wide_candidates(
				frame,
				region,
				mask,
				expected_width,
				expected_height,
			)
		)

		return self._deduplicate(
			result
		)

	def _split_wide_candidates(
		self,
		frame,
		region,
		mask,
		expected_width,
		expected_height,
	):
		"""
		Если chips/morphology визуально связали несколько карт,
		широкий светлый blob не выбрасывается — разбирается по vertical
		projection на несколько card-width slots.
		"""
		x1, y1, _, _ = region

		contours, _ = cv2.findContours(
			mask,
			cv2.RETR_EXTERNAL,
			cv2.CHAIN_APPROX_SIMPLE,
		)

		result = []

		for contour in contours:
			x, y, width, height = (
				cv2.boundingRect(
					contour
				)
			)

			if (
				width
				< expected_width * 1.45
			):
				continue

			if not (
				expected_height * 0.38
				<= height
				<= expected_height * 1.30
			):
				continue

			count = int(
				round(
					width
					/ max(
						expected_width,
						1,
					)
				)
			)

			count = max(
				2,
				min(
					5,
					count,
				),
			)

			step = (
				width
				/ float(
					count
				)
			)

			for index in range(
				count
			):
				center_x = (
					x
					+ step
					* (
						index
						+ 0.5
					)
				)

				card_x = int(
					round(
						x1
						+ center_x
						- expected_width / 2
					)
				)

				card_y = (
					y1 + y
				)

				result.append(
					CardBox(
						x=card_x,
						y=card_y,
						width=expected_width,
						height=expected_height,
					)
				)

		return result

	def _regular_row(
		self,
		group,
	):
		if len(group) != 3:
			return False

		group = sorted(
			group,
			key=lambda card: card.x,
		)

		widths = [
			card.width
			for card in group
		]

		heights = [
			card.height
			for card in group
		]

		if (
			min(widths)
			/ max(
				max(widths),
				1,
			)
			< 0.72
		):
			return False

		if (
			min(heights)
			/ max(
				max(heights),
				1,
			)
			< 0.72
		):
			return False

		y_span = (
			max(
				card.center[1]
				for card in group
			)
			- min(
				card.center[1]
				for card in group
			)
		)

		if (
			y_span
			> np.median(
				heights
			) * 0.25
		):
			return False

		pitch_a = (
			group[1].center[0]
			- group[0].center[0]
		)

		pitch_b = (
			group[2].center[0]
			- group[1].center[0]
		)

		if (
			pitch_a <= 0
			or pitch_b <= 0
		):
			return False

		return (
			min(
				pitch_a,
				pitch_b,
			)
			/ max(
				pitch_a,
				pitch_b,
			)
			>= 0.72
		)

	def _refine_expected_card(
		self,
		frame,
		expected,
		search_x,
		search_y,
	):
		best = self._clip_box(
			frame,
			expected,
		)

		best_score = (
			self._card_evidence(
				frame,
				best,
				top_fraction=0.62,
			)
		)

		step_x = max(
			2,
			search_x // 4,
		)

		step_y = max(
			2,
			search_y // 3,
		)

		for dy in range(
			-search_y,
			search_y + 1,
			step_y,
		):
			for dx in range(
				-search_x,
				search_x + 1,
				step_x,
			):
				candidate = CardBox(
					x=expected.x + dx,
					y=expected.y + dy,
					width=expected.width,
					height=expected.height,
				)

				candidate = (
					self._clip_box(
						frame,
						candidate,
					)
				)

				score = (
					self._card_evidence(
						frame,
						candidate,
						top_fraction=0.62,
					)
				)

				# Небольшой штраф за уход далеко от expected geometry.
				score -= (
					abs(dx)
					/ max(
						expected.width,
						1,
					)
					* 0.035
				)

				score -= (
					abs(dy)
					/ max(
						expected.height,
						1,
					)
					* 0.035
				)

				if score > best_score:
					best = candidate
					best_score = score

		return best

	def _card_evidence(
		self,
		frame,
		box,
		top_fraction,
	):
		box = self._clip_box(
			frame,
			box,
		)

		if (
			box.width <= 2
			or box.height <= 4
		):
			return 0.0

		visible_height = max(
			4,
			int(
				round(
					box.height
					* top_fraction
				)
			),
		)

		crop = frame[
			box.y:(
				box.y
				+ min(
					box.height,
					visible_height,
				)
			),
			box.x:(
				box.x
				+ box.width
			),
		]

		if crop.size == 0:
			return 0.0

		hsv = cv2.cvtColor(
			crop,
			cv2.COLOR_BGR2HSV,
		)

		mask = cv2.inRange(
			hsv,
			self.white_low,
			self.white_high,
		)

		white_ratio = (
			cv2.countNonZero(
				mask
			)
			/ float(
				mask.shape[0]
				* mask.shape[1]
			)
		)

		# У настоящей карты есть светлая область почти по всей ширине.
		column_fill = (
			np.count_nonzero(
				np.mean(
					mask > 0,
					axis=0,
				)
				>= 0.28
			)
			/ float(
				max(
					mask.shape[1],
					1,
				)
			)
		)

		return (
			white_ratio * 0.68
			+ column_fill * 0.32
		)

	def _white_mask(
		self,
		frame,
		region,
	):
		x1, y1, x2, y2 = (
			region
		)

		x1 = max(
			0,
			int(x1),
		)

		y1 = max(
			0,
			int(y1),
		)

		x2 = min(
			frame.shape[1],
			int(x2),
		)

		y2 = min(
			frame.shape[0],
			int(y2),
		)

		if (
			x2 <= x1
			or y2 <= y1
		):
			return None

		crop = frame[
			y1:y2,
			x1:x2,
		]

		hsv = cv2.cvtColor(
			crop,
			cv2.COLOR_BGR2HSV,
		)

		mask = cv2.inRange(
			hsv,
			self.white_low,
			self.white_high,
		)

		# Только лёгкая чистка. Большой CLOSE раньше физически склеивал
		# соседние карты и chips с картами.
		mask = cv2.morphologyEx(
			mask,
			cv2.MORPH_OPEN,
			cv2.getStructuringElement(
				cv2.MORPH_RECT,
				(2, 2),
			),
			iterations=1,
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

		return mask

	def _expected_card_size(
		self,
		frame,
	):
		if (
			self.card_size_hint
			is not None
		):
			return (
				int(
					self.card_size_hint[0]
				),
				int(
					self.card_size_hint[1]
				),
			)

		height, _ = (
			frame.shape[:2]
		)

		card_height = max(
			36,
			int(
				round(
					height
					* 0.115
				)
			),
		)

		card_width = max(
			22,
			int(
				round(
					card_height
					* 0.70
				)
			),
		)

		return (
			card_width,
			card_height,
		)

	def _deduplicate(
		self,
		cards,
	):
		result = []

		for card in sorted(
			cards,
			key=lambda item: (
				item.width
				* item.height
			),
			reverse=True,
		):
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
					< min(
						card.width,
						existing.width,
					) * 0.52
				):
					duplicate = True
					break

			if not duplicate:
				result.append(
					card
				)

		return result

	def _clip_box(
		self,
		frame,
		box,
	):
		frame_height, frame_width = (
			frame.shape[:2]
		)

		x = max(
			0,
			min(
				int(box.x),
				frame_width - 1,
			),
		)

		y = max(
			0,
			min(
				int(box.y),
				frame_height - 1,
			),
		)

		width = max(
			1,
			min(
				int(box.width),
				frame_width - x,
			),
		)

		height = max(
			1,
			min(
				int(box.height),
				frame_height - y,
			),
		)

		return CardBox(
			x=x,
			y=y,
			width=width,
			height=height,
		)


def crop_card(
	frame,
	card,
):
	x1, y1, x2, y2 = (
		card.rect
	)

	return frame[
		y1:y2,
		x1:x2,
	]
