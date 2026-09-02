import re

import cv2
import numpy as np
import pytesseract

from poker.vision.ocr.tesseract_runtime import TESSERACT_RUNTIME


class PotReader:
	def read(self, table_frame):
		height, width = table_frame.shape[:2]

		roi = table_frame[
			int(height * 0.25):int(height * 0.48),
			int(width * 0.31):int(width * 0.69),
		]

		if roi.size == 0:
			return None

		hsv = cv2.cvtColor(
			roi,
			cv2.COLOR_BGR2HSV,
		)

		# Текст "Банк:" в PokerDom ярко-зелёный.
		mask = cv2.inRange(
			hsv,
			np.array([38, 65, 75], dtype=np.uint8),
			np.array([92, 255, 255], dtype=np.uint8),
		)

		contours, _ = cv2.findContours(
			mask,
			cv2.RETR_EXTERNAL,
			cv2.CHAIN_APPROX_SIMPLE,
		)

		if not contours:
			return None

		points = np.vstack(
			contours
		)

		x, y, box_width, box_height = cv2.boundingRect(
			points
		)

		if box_width < roi.shape[1] * 0.08:
			return None

		pad_x = max(
			8,
			int(box_width * 0.12),
		)

		pad_y = max(
			5,
			int(box_height * 0.35),
		)

		x1 = max(
			0,
			x - pad_x,
		)
		y1 = max(
			0,
			y - pad_y,
		)
		x2 = min(
			roi.shape[1],
			x + box_width + pad_x,
		)
		y2 = min(
			roi.shape[0],
			y + box_height + pad_y,
		)

		text_roi = roi[
			y1:y2,
			x1:x2,
		]

		gray = cv2.cvtColor(
			text_roi,
			cv2.COLOR_BGR2GRAY,
		)

		gray = cv2.resize(
			gray,
			None,
			fx=2.5,
			fy=2.5,
			interpolation=cv2.INTER_CUBIC,
		)

		text = pytesseract.image_to_string(
			gray,
			lang="rus+eng",
			config=(
				"--psm 7 "
				"-c tessedit_char_whitelist="
				"БанкBANKbank0123456789,.рР "
			),
		)

		return self._parse(
			text
		)

	def _parse(self, text):
		if not text:
			return None

		match = re.search(
			r"(\d+(?:[.,]\d{1,2})?)",
			text.replace(" ", ""),
		)

		if not match:
			return None

		try:
			return float(
				match.group(1).replace(
					",",
					".",
				)
			)
		except ValueError:
			return None
