from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class PlayerPanel:
	x: int
	y: int
	width: int
	height: int

	@property
	def center(self):
		return (
			self.x + self.width // 2,
			self.y + self.height // 2,
		)

	@property
	def rect(self):
		return (
			self.x,
			self.y,
			self.x + self.width,
			self.y + self.height,
		)


class PlayerPanelDetector:
	def __init__(self):
		self.last_panels = []
		self._pending_count = None
		self._pending_count_hits = 0

	def detect(self, table_frame):
		height, width = table_frame.shape[:2]

		gray = cv2.cvtColor(
			table_frame,
			cv2.COLOR_BGR2GRAY,
		)

		gray = cv2.medianBlur(
			gray,
			5,
		)

		scale = width / 1240.0

		min_radius = max(
			35,
			int(round(60 * scale)),
		)

		max_radius = max(
			min_radius + 8,
			int(round(90 * scale)),
		)

		min_distance = max(
			80,
			int(round(120 * scale)),
		)

		circles = cv2.HoughCircles(
			gray,
			cv2.HOUGH_GRADIENT,
			dp=1.2,
			minDist=min_distance,
			param1=100,
			param2=45,
			minRadius=min_radius,
			maxRadius=max_radius,
		)

		if circles is None:
			return self.last_panels

		avatar_circles = []

		for x, y, radius in np.round(
			circles[0]
		).astype(int):
			rel_x = x / width
			rel_y = y / height

			is_perimeter = (
				rel_y < 0.22
				or rel_y > 0.60
				or rel_x < 0.24
				or rel_x > 0.76
			)

			if not is_perimeter:
				continue

			if rel_y > 0.86:
				continue

			avatar_circles.append(
				(x, y, radius)
			)

		avatar_circles = self._deduplicate_circles(
			avatar_circles,
		)

		panels = []

		for circle in avatar_circles:
			predicted = self._panel_from_avatar(
				circle,
				width,
				height,
			)

			refined = self._refine_panel(
				table_frame,
				predicted,
			)

			panels.append(
				refined or predicted
			)

		panels = sorted(
			panels,
			key=self._clockwise_key(
				width,
				height,
			),
		)

		panels = panels[:10]

		return self._stabilize(
			panels
		)

	def _refine_panel(
		self,
		table_frame,
		predicted,
	):
		frame_height, frame_width = table_frame.shape[:2]

		pad_x = int(round(predicted.width * 0.30))
		pad_y = int(round(predicted.height * 0.30))

		x1 = max(0, predicted.x - pad_x)
		y1 = max(0, predicted.y - pad_y)
		x2 = min(
			frame_width,
			predicted.x + predicted.width + pad_x,
		)
		y2 = min(
			frame_height,
			predicted.y + predicted.height + pad_y,
		)

		search = table_frame[
			y1:y2,
			x1:x2,
		]

		if search.size == 0:
			return None

		gray = cv2.cvtColor(
			search,
			cv2.COLOR_BGR2GRAY,
		)

		# Плашка почти чёрная. Иконки действий/статуса могут быть яркими,
		# но они не должны определять её внешнюю геометрию.
		mask = cv2.inRange(
			gray,
			0,
			72,
		)

		mask = cv2.morphologyEx(
			mask,
			cv2.MORPH_CLOSE,
			cv2.getStructuringElement(
				cv2.MORPH_RECT,
				(9, 5),
			),
			iterations=2,
		)

		contours, _ = cv2.findContours(
			mask,
			cv2.RETR_EXTERNAL,
			cv2.CHAIN_APPROX_SIMPLE,
		)

		best = None
		best_score = -1.0

		predicted_center = predicted.center

		for contour in contours:
			cx, cy, cw, ch = cv2.boundingRect(
				contour
			)

			if cw < predicted.width * 0.65:
				continue

			if cw > predicted.width * 1.35:
				continue

			if ch < predicted.height * 0.55:
				continue

			if ch > predicted.height * 1.55:
				continue

			absolute_x = x1 + cx
			absolute_y = y1 + cy

			center_x = absolute_x + cw / 2
			center_y = absolute_y + ch / 2

			distance = np.hypot(
				center_x - predicted_center[0],
				center_y - predicted_center[1],
			)

			size_score = min(
				cw / max(predicted.width, 1),
				predicted.width / max(cw, 1),
			)

			distance_score = max(
				0.0,
				1.0 - distance / max(predicted.width, 1),
			)

			score = (
				size_score * 0.65
				+ distance_score * 0.35
			)

			if score > best_score:
				best_score = score
				best = PlayerPanel(
					x=absolute_x,
					y=absolute_y,
					width=cw,
					height=ch,
				)

		return best

	def _stabilize(self, panels):
		if not panels:
			return self.last_panels

		new_count = len(panels)
		old_count = len(self.last_panels)

		if old_count == 0:
			self.last_panels = panels
			self._reset_pending()
			return self.last_panels

		if new_count == old_count:
			self.last_panels = panels
			self._reset_pending()
			return self.last_panels

		if new_count > old_count:
			self.last_panels = panels
			self._reset_pending()
			return self.last_panels

		if self._pending_count == new_count:
			self._pending_count_hits += 1
		else:
			self._pending_count = new_count
			self._pending_count_hits = 1

		if self._pending_count_hits >= 3:
			self.last_panels = panels
			self._reset_pending()

		return self.last_panels

	def _reset_pending(self):
		self._pending_count = None
		self._pending_count_hits = 0

	def _panel_from_avatar(
		self,
		circle,
		frame_width,
		frame_height,
	):
		center_x, center_y, radius = circle

		panel_width = int(
			round(radius * 2.08)
		)

		panel_height = int(
			round(radius * 0.78)
		)

		panel_left = int(
			round(
				center_x
				- panel_width / 2
			)
		)

		panel_top = int(
			round(
				center_y
				+ radius * 0.72
			)
		)

		panel_left = max(
			0,
			min(
				panel_left,
				frame_width - panel_width,
			),
		)

		panel_top = max(
			0,
			min(
				panel_top,
				frame_height - panel_height,
			),
		)

		return PlayerPanel(
			x=panel_left,
			y=panel_top,
			width=panel_width,
			height=panel_height,
		)

	def _deduplicate_circles(
		self,
		circles,
	):
		result = []

		for circle in sorted(
			circles,
			key=lambda value: value[2],
			reverse=True,
		):
			x, y, radius = circle
			duplicate = False

			for existing in result:
				ex, ey, er = existing

				distance = np.hypot(
					x - ex,
					y - ey,
				)

				if distance < max(
					radius,
					er,
				) * 1.45:
					duplicate = True
					break

			if not duplicate:
				result.append(circle)

		return result

	def _clockwise_key(
		self,
		frame_width,
		frame_height,
	):
		center_x = frame_width / 2
		center_y = frame_height * 0.47

		def key(panel):
			x, y = panel.center

			angle = np.arctan2(
				y - center_y,
				x - center_x,
			)

			return (
				angle + np.pi / 2
			) % (2 * np.pi)

		return key


def crop_panel(
	table_frame,
	panel,
):
	x1, y1, x2, y2 = panel.rect

	return table_frame[
		y1:y2,
		x1:x2,
	]


def _compute_name_top_offset(
	panel_frame,
):
	if panel_frame.size == 0:
		return 0

	height, width = panel_frame.shape[:2]

	search_height = max(
		1,
		int(round(height * 0.32)),
	)

	upper = panel_frame[
		:search_height,
		:,
	]

	hsv = cv2.cvtColor(
		upper,
		cv2.COLOR_BGR2HSV,
	)

	saturation = hsv[:, :, 1]
	value = hsv[:, :, 2]

	white_mask = np.where(
		(value >= 148)
		& (saturation <= 72),
		255,
		0,
	).astype(np.uint8)

	white_mask = cv2.morphologyEx(
		white_mask,
		cv2.MORPH_OPEN,
		cv2.getStructuringElement(
			cv2.MORPH_RECT,
			(2, 2),
		),
		iterations=1,
	)

	white_mask = cv2.morphologyEx(
		white_mask,
		cv2.MORPH_CLOSE,
		cv2.getStructuringElement(
			cv2.MORPH_RECT,
			(5, 2),
		),
		iterations=1,
	)

	contours, _ = cv2.findContours(
		white_mask,
		cv2.RETR_EXTERNAL,
		cv2.CHAIN_APPROX_SIMPLE,
	)

	exclusion_bottom = 0
	min_width = max(
		5,
		int(round(width * 0.05)),
	)
	max_height = max(
		4,
		int(round(height * 0.16)),
	)

	for contour in contours:
		x, y, w, h = cv2.boundingRect(
			contour
		)

		if y > 6:
			continue

		if w < min_width:
			continue

		if h > max_height:
			continue

		aspect_ratio = (
			w
			/ max(
				h,
				1,
			)
		)

		is_rim_like = (
			w
			>= int(
				round(
					width * 0.18
				)
			)
			or aspect_ratio >= 2.0
		)

		if not is_rim_like:
			continue

		exclusion_bottom = max(
			exclusion_bottom,
			y + h,
		)

	if white_mask.size != 0:
		row_fill = np.mean(
			white_mask > 0,
			axis=1,
		)

		row_run = 0
		row_cut = 0

		for index, fill in enumerate(
			row_fill
		):
			if fill >= 0.08:
				row_run += 1
				row_cut = index + 1
				continue

			if row_run >= 2:
				break

			if index >= 4:
				break

		if row_cut > 0:
			exclusion_bottom = max(
				exclusion_bottom,
				row_cut,
			)

	if exclusion_bottom <= 0:
		return 0

	return min(
		exclusion_bottom + 3,
		int(round(height * 0.26)),
	)


def crop_name_from_panel(
	panel_frame,
):
	if panel_frame.size == 0:
		return panel_frame

	height, width = panel_frame.shape[:2]

	base_top = int(
		round(
			height * 0.09
		)
	)

	top = max(
		base_top,
		_compute_name_top_offset(
			panel_frame
		),
	)

	top = min(
		top,
		int(
			round(
				height * 0.20
			)
		),
	)

	bottom = int(
		round(
			height * 0.50
		)
	)

	left = int(
		width * 0.02
	)

	right = int(
		width * 0.99
	)

	if bottom <= top:
		top = int(
			round(
				height * 0.10
			)
		)

		bottom = int(
			round(
				height * 0.50
			)
		)

	return panel_frame[
		top:bottom,
		left:right,
	]
