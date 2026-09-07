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
		self.hero_pair_hint = None
		self.hero_pair_misses = 0

		# HERO panel detector немного гуляет между кадрами, а реальные
		# hole cards обычно остаются неподвижными. Поэтому отдельно
		# держим устойчивую геометрию пары и используем panel только
		# для первичного захвата / проверки, что HERO не переехал.
		self.hero_pair_hint = None
		self.hero_pair_misses = 0

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

		center_x = float(
			hero_panel.center[0]
		)

		# Сначала пробуем temporal lock. В присланных captures player panel
		# менял Y примерно на 15 px, тогда как реальные карты держались
		# практически на одной координате. Поэтому после первого хорошего
		# захвата не следуем за jitter панели.
		locked = self._hero_pair_from_hint(
			table_frame,
			hero_panel,
			card_width,
			card_height,
			gap,
		)

		if locked:
			self.hero_pair_misses = 0
			self._remember_hero_pair(
				locked
			)
			return locked

		self.hero_pair_misses += 1

		# Полный reacquire. Panel нужен только как грубая опора.
		# Верх карты ищется joint-refinement сразу для ПАРЫ, поэтому две
		# рамки не могут независимо разъехаться по Y.
		pair_width = (
			card_width * 2
			+ gap
		)

		base_y = int(
			round(
				hero_panel.y
				- card_height * 0.94
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

		result = self._refine_hero_pair(
			table_frame,
			expected,
			search_x=max(
				4,
				int(
					round(
						card_width * 0.16
					)
				),
			),
			search_y_up=max(
				5,
				int(
					round(
						card_height * 0.18
					)
				),
			),
			search_y_down=max(
				2,
				int(
					round(
						card_height * 0.045
					)
				),
			),
		)

		if not result:
			if self.hero_pair_misses >= 4:
				self.hero_pair_hint = None
			return []

		center_distance = abs(
			(
				result[0].center[0]
				+ result[1].center[0]
			) / 2.0
			- center_x
		)

		if (
			center_distance
			> card_width * 0.50
		):
			return []

		self.hero_pair_misses = 0
		self._remember_hero_pair(
			result
		)

		return result

	def _hero_pair_from_hint(
		self,
		frame,
		hero_panel,
		card_width,
		card_height,
		gap,
	):
		hint = self.hero_pair_hint

		if not hint:
			return []

		hint_center_x = float(
			hint["center_x"]
		)

		panel_center_x = float(
			hero_panel.center[0]
		)

		# HERO сменил место / stale lock.
		if (
			abs(
				hint_center_x
				- panel_center_x
			)
			> card_width * 0.75
		):
			self.hero_pair_hint = None
			return []

		first_x = int(
			round(
				panel_center_x
				- (
					card_width * 2
					+ gap
				) / 2.0
			)
		)

		base_y = int(
			round(
				hint["y"]
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

		# Locked path очень маленький и потому заметно дешевле полного
		# reacquire. Одновременно это не даёт ROI прыгать за panel jitter.
		return self._refine_hero_pair(
			frame,
			expected,
			search_x=max(
				2,
				int(
					round(
						card_width * 0.055
					)
				),
			),
			search_y_up=max(
				2,
				int(
					round(
						card_height * 0.055
					)
				),
			),
			search_y_down=max(
				1,
				int(
					round(
						card_height * 0.025
					)
				),
			),
			min_score=0.20,
		)

	def _refine_hero_pair(
		self,
		frame,
		expected,
		search_x,
		search_y_up,
		search_y_down,
		min_score=0.17,
	):
		if len(expected) != 2:
			return []

		best = None
		best_score = None

		step_x = max(
			1,
			search_x // 4,
		)

		step_y = max(
			1,
			max(
				search_y_up,
				search_y_down,
			) // 5,
		)

		for dy in range(
			-search_y_up,
			search_y_down + 1,
			step_y,
		):
			for dx in range(
				-search_x,
				search_x + 1,
				step_x,
			):
				pair = [
					self._clip_box(
						frame,
						CardBox(
							x=box.x + dx,
							y=box.y + dy,
							width=box.width,
							height=box.height,
						),
					)
					for box in expected
				]

				left_score = (
					self._hero_alignment_score(
						frame,
						pair[0],
					)
				)

				right_score = (
					self._hero_alignment_score(
						frame,
						pair[1],
					)
				)

				# Обе карты должны иметь evidence. Одна сильная карта
				# больше не может "утащить" пару в неправильный Y.
				weakest = min(
					left_score,
					right_score,
				)

				score = (
					(
						left_score
						+ right_score
					) * 0.40
					+ weakest * 0.35
				)

				score -= (
					abs(dx)
					/ max(
						expected[0].width,
						1,
					)
					* 0.045
				)

				if dy > 0:
					score -= (
						dy
						/ max(
							expected[0].height,
							1,
						)
						* 0.42
					)
				else:
					score -= (
						abs(dy)
						/ max(
							expected[0].height,
							1,
						)
						* 0.035
					)

				if (
					best_score is None
					or score > best_score
				):
					best_score = score
					best = pair

		if (
			best is None
			or best_score is None
			or best_score < min_score
		):
			return []

		return sorted(
			best,
			key=lambda card: card.x,
		)

	def _remember_hero_pair(
		self,
		cards,
	):
		if len(cards) != 2:
			return

		center_x = (
			cards[0].center[0]
			+ cards[1].center[0]
		) / 2.0

		y = (
			cards[0].y
			+ cards[1].y
		) / 2.0

		if self.hero_pair_hint is None:
			self.hero_pair_hint = {
				"center_x": center_x,
				"y": y,
			}
			return

		# Небольшое EMA: реальная карта может сдвинуться при resize,
		# но единичный jitter не двигает lock.
		self.hero_pair_hint = {
			"center_x": (
				self.hero_pair_hint[
					"center_x"
				] * 0.78
				+ center_x * 0.22
			),
			"y": (
				self.hero_pair_hint[
					"y"
				] * 0.84
				+ y * 0.16
			),
		}

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
		search_y_up,
		search_y_down,
	):
		best = self._clip_box(
			frame,
			expected,
		)

		best_score = (
			self._hero_alignment_score(
				frame,
				best,
			)
		)

		step_x = max(
			2,
			search_x // 4,
		)

		step_y = max(
			2,
			max(
				search_y_up,
				search_y_down,
			) // 4,
		)

		for dy in range(
			-search_y_up,
			search_y_down + 1,
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
					self._hero_alignment_score(
						frame,
						candidate,
					)
				)

				score -= (
					abs(dx)
					/ max(
						expected.width,
						1,
					)
					* 0.055
				)

				if dy > 0:
					score -= (
						dy
						/ max(
							expected.height,
							1,
						)
						* 0.38
					)
				else:
					score -= (
						abs(dy)
						/ max(
							expected.height,
							1,
						)
						* 0.055
					)

				if score > best_score:
					best = candidate
					best_score = score

		return best

	def _hero_alignment_score(
		self,
		frame,
		box,
	):
		"""
		HERO ROI должен попадать именно в верх карты.

		Просто большой процент белого недостаточен: box на несколько
		пикселей ниже всё ещё содержит много белого, но rank/suit corner
		уже съезжает и даёт ошибки вроде 6->T и Q->8.
		"""
		box = self._clip_box(
			frame,
			box,
		)

		if (
			box.width <= 4
			or box.height <= 8
		):
			return 0.0

		top_band_height = max(
			3,
			int(
				round(
					box.height * 0.10
				)
			),
		)

		upper_height = max(
			8,
			int(
				round(
					box.height * 0.48
				)
			),
		)

		inside = frame[
			box.y:min(
				frame.shape[0],
				box.y + upper_height,
			),
			box.x:min(
				frame.shape[1],
				box.x + box.width,
			),
		]

		if inside.size == 0:
			return 0.0

		hsv = cv2.cvtColor(
			inside,
			cv2.COLOR_BGR2HSV,
		)

		mask = cv2.inRange(
			hsv,
			self.white_low,
			self.white_high,
		)

		top_band = mask[
			0:min(
				top_band_height,
				mask.shape[0],
			),
			:,
		]

		top_white = (
			cv2.countNonZero(
				top_band
			)
			/ float(
				max(
					top_band.size,
					1,
				)
			)
		)

		upper_white = (
			cv2.countNonZero(
				mask
			)
			/ float(
				max(
					mask.size,
					1,
				)
			)
		)

		above_height = max(
			3,
			int(
				round(
					box.height * 0.08
				)
			),
		)

		above_y1 = max(
			0,
			box.y - above_height,
		)

		above = frame[
			above_y1:box.y,
			box.x:min(
				frame.shape[1],
				box.x + box.width,
			),
		]

		above_white = 0.0

		if above.size:
			above_hsv = cv2.cvtColor(
				above,
				cv2.COLOR_BGR2HSV,
			)

			above_mask = cv2.inRange(
				above_hsv,
				self.white_low,
				self.white_high,
			)

			above_white = (
				cv2.countNonZero(
					above_mask
				)
				/ float(
					max(
						above_mask.size,
						1,
					)
				)
			)

		return (
			top_white * 0.52
			+ upper_white * 0.38
			+ max(
				0.0,
				top_white - above_white,
			) * 0.22
			- above_white * 0.20
		)


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
