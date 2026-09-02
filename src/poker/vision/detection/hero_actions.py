from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class ActionButton:
	action: str
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


@dataclass(frozen=True)
class HeroActionState:
	is_my_turn: bool
	can_fold: bool
	can_check: bool
	can_call: bool
	can_bet: bool
	can_raise: bool
	can_all_in: bool
	buttons: tuple


class HeroActionDetector:
	def detect(self, table_frame):
		height, width = table_frame.shape[:2]

		# Активные кнопки PokerDom находятся в нижней центральной части.
		x1 = int(width * 0.24)
		y1 = int(height * 0.78)
		x2 = int(width * 0.78)
		y2 = height

		roi = table_frame[
			y1:y2,
			x1:x2,
		]

		if roi.size == 0:
			return self._empty()

		hsv = cv2.cvtColor(
			roi,
			cv2.COLOR_BGR2HSV,
		)

		masks = {
			"fold": cv2.inRange(
				hsv,
				np.array([38, 90, 70], dtype=np.uint8),
				np.array([92, 255, 255], dtype=np.uint8),
			),
			"call": cv2.inRange(
				hsv,
				np.array([12, 105, 90], dtype=np.uint8),
				np.array([38, 255, 255], dtype=np.uint8),
			),
			"raise": self._red_mask(
				hsv
			),
		}

		buttons = []

		for action, mask in masks.items():
			buttons.extend(
				self._find_buttons(
					mask,
					action,
					x1,
					y1,
					width,
					height,
				)
			)

		buttons = self._deduplicate(
			buttons
		)

		actions = {
			button.action
			for button in buttons
		}

		# Активный ход отличается именно цветными крупными кнопками.
		is_my_turn = len(buttons) >= 2

		return HeroActionState(
			is_my_turn=is_my_turn,
			can_fold="fold" in actions,
			can_check=False,
			can_call="call" in actions,
			can_bet=False,
			can_raise="raise" in actions,
			can_all_in=False,
			buttons=tuple(buttons),
		)

	def _red_mask(self, hsv):
		low = cv2.inRange(
			hsv,
			np.array([0, 105, 90], dtype=np.uint8),
			np.array([10, 255, 255], dtype=np.uint8),
		)

		high = cv2.inRange(
			hsv,
			np.array([168, 105, 90], dtype=np.uint8),
			np.array([179, 255, 255], dtype=np.uint8),
		)

		return cv2.bitwise_or(
			low,
			high,
		)

	def _find_buttons(
		self,
		mask,
		action,
		offset_x,
		offset_y,
		frame_width,
		frame_height,
	):
		mask = cv2.morphologyEx(
			mask,
			cv2.MORPH_CLOSE,
			cv2.getStructuringElement(
				cv2.MORPH_RECT,
				(11, 7),
			),
			iterations=2,
		)

		contours, _ = cv2.findContours(
			mask,
			cv2.RETR_EXTERNAL,
			cv2.CHAIN_APPROX_SIMPLE,
		)

		result = []

		for contour in contours:
			x, y, width, height = cv2.boundingRect(
				contour
			)

			if width < frame_width * 0.09:
				continue

			if width > frame_width * 0.23:
				continue

			if height < frame_height * 0.045:
				continue

			if height > frame_height * 0.12:
				continue

			aspect = width / max(
				height,
				1,
			)

			if not 1.6 <= aspect <= 4.7:
				continue

			result.append(
				ActionButton(
					action=action,
					x=offset_x + x,
					y=offset_y + y,
					width=width,
					height=height,
				)
			)

		return result

	def _deduplicate(
		self,
		buttons,
	):
		result = []

		for button in sorted(
			buttons,
			key=lambda value: value.width * value.height,
			reverse=True,
		):
			duplicate = False

			for existing in result:
				dx = abs(
					(
						button.x
						+ button.width / 2
					)
					- (
						existing.x
						+ existing.width / 2
					)
				)

				dy = abs(
					(
						button.y
						+ button.height / 2
					)
					- (
						existing.y
						+ existing.height / 2
					)
				)

				if (
					dx < max(
						button.width,
						existing.width,
					) * 0.35
					and dy < max(
						button.height,
						existing.height,
					) * 0.45
				):
					duplicate = True
					break

			if not duplicate:
				result.append(button)

		return result

	def _empty(self):
		return HeroActionState(
			is_my_turn=False,
			can_fold=False,
			can_check=False,
			can_call=False,
			can_bet=False,
			can_raise=False,
			can_all_in=False,
			buttons=tuple(),
		)
