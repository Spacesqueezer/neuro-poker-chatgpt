from pathlib import Path
import time

import cv2
import numpy as np

from poker.vision.detection.player_panels import (
	crop_name_from_panel,
	crop_panel,
)
from poker.vision.recognition.name_character_templates import (
	normalize_name_crop,
)


class FastHeroLocator:
	def __init__(
		self,
		project_root,
		hero_name,
	):
		self.project_root = Path(
			project_root
		)

		self.hero_name = (
			hero_name
			.strip()
			.lower()
		)

		self.templates = []
		self.cached_center = None
		self.cached_normalized_center = None
		self.last_confirmed_at = 0.0
		self.hold_seconds = 12.0

		self._load_templates()

	def _load_templates(self):
		folder = (
			self.project_root
			/ "assets"
			/ "players"
			/ "templates"
			/ "names"
			/ self.hero_name
		)

		if not folder.exists():
			return

		for path in folder.glob(
			"*.png"
		):
			image = cv2.imread(
				str(path),
				cv2.IMREAD_GRAYSCALE,
			)

			if image is None:
				continue

			self.templates.append(
				image
			)

	def remember(
		self,
		panel,
		table_shape=None,
	):
		if panel is None:
			return

		self.cached_center = (
			float(
				panel.center[0]
			),
			float(
				panel.center[1]
			),
		)

		if table_shape is not None:
			height, width = (
				table_shape[:2]
			)

			if width > 0 and height > 0:
				self.cached_normalized_center = (
					self.cached_center[0]
					/ width,
					self.cached_center[1]
					/ height,
				)

		self.last_confirmed_at = (
			time.monotonic()
		)

	def reset(self):
		self.cached_center = None
		self.cached_normalized_center = None
		self.last_confirmed_at = 0.0

	def locate(
		self,
		table_frame,
		panels,
	):
		if not panels:
			return None

		# Сначала держимся за уже известное физическое место HERO.
		cached = self._nearest_cached(
			panels,
			table_frame.shape,
		)

		if cached is not None:
			return cached

		# Если есть full-name templates "spacesqueezer", HERO можно
		# найти без Tesseract за миллисекунды.
		if not self.templates:
			return None

		best_panel = None
		best_score = 0.0

		for panel in panels:
			panel_frame = crop_panel(
				table_frame,
				panel,
			)

			name_frame = crop_name_from_panel(
				panel_frame
			)

			score = self._score_name(
				name_frame
			)

			if score > best_score:
				best_score = score
				best_panel = panel

		if (
			best_panel is not None
			and best_score >= 0.64
		):
			self.remember(
				best_panel,
				table_frame.shape,
			)

			return best_panel

		return None

	def _nearest_cached(
		self,
		panels,
		table_shape,
	):
		if (
			self.cached_center is None
			and self.cached_normalized_center
			is None
		):
			return None

		height, width = (
			table_shape[:2]
		)

		if (
			self.cached_normalized_center
			is not None
			and width > 0
			and height > 0
		):
			reference_center = (
				self.cached_normalized_center[0]
				* width,
				self.cached_normalized_center[1]
				* height,
			)
		else:
			reference_center = (
				self.cached_center
			)

		best = None
		best_distance = None

		for panel in panels:
			distance = float(
				np.hypot(
					panel.center[0]
					- reference_center[0],
					panel.center[1]
					- reference_center[1],
				)
			)

			if (
				best_distance is None
				or distance < best_distance
			):
				best = panel
				best_distance = distance

		if best is None:
			return None

		threshold = max(
			35.0,
			float(
				best.width
			)
			* 1.15,
		)

		if best_distance > threshold:
			# Короткий detector miss / дрожание panels не должно сразу
			# уничтожать HERO lock. Но чужую далёкую panel не принимаем.
			if (
				time.monotonic()
				- self.last_confirmed_at
				<= self.hold_seconds
			):
				return None

			self.reset()
			return None

		self.remember(
			best,
			table_shape,
		)

		return best

	def _score_name(
		self,
		image,
	):
		if (
			image is None
			or image.size == 0
		):
			return 0.0

		binary = normalize_name_crop(
			image
		)

		if binary is None:
			return 0.0

		target_height = 42

		scale = (
			target_height
			/ max(
				binary.shape[0],
				1,
			)
		)

		target_width = max(
			1,
			int(
				round(
					binary.shape[1]
					* scale
				)
			),
		)

		candidate = cv2.resize(
			binary,
			(
				target_width,
				target_height,
			),
			interpolation=cv2.INTER_AREA,
		)

		best = 0.0

		for template in self.templates:
			if template.size == 0:
				continue

			width_ratio = (
				candidate.shape[1]
				/ max(
					template.shape[1],
					1,
				)
			)

			if not (
				0.72
				<= width_ratio
				<= 1.38
			):
				continue

			resized = cv2.resize(
				candidate,
				(
					template.shape[1],
					template.shape[0],
				),
				interpolation=cv2.INTER_AREA,
			)

			left = (
				resized > 127
			).astype(
				np.uint8
			)

			right = (
				template > 127
			).astype(
				np.uint8
			)

			intersection = np.count_nonzero(
				left & right
			)

			union = np.count_nonzero(
				left | right
			)

			if union <= 0:
				continue

			iou = (
				intersection
				/ float(
					union
				)
			)

			diff = cv2.absdiff(
				resized,
				template,
			)

			pixel_score = max(
				0.0,
				1.0
				- float(
					np.mean(
						diff
					)
				)
				/ 255.0,
			)

			score = (
				iou * 0.70
				+ pixel_score * 0.30
			)

			best = max(
				best,
				score,
			)

		return best
