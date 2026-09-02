import re

import cv2
import numpy as np
import pytesseract

from poker.vision.ocr.tesseract_runtime import TESSERACT_RUNTIME


ACTION_ALIASES = {
	"СБРАСЫВАЕТ": "fold",
	"ФОЛД": "fold",
	"ЧЕК": "check",
	"УРАВНИВАЕТ": "call",
	"СТАВИТ": "bet",
	"ПОДНИМАЕТ": "raise",
	"ВА-БАНК": "all_in",
	"ВАБАНК": "all_in",
	"ALL-IN": "all_in",
}


def _normalize_text(value):
	value = value.upper().strip()
	return re.sub(
		r"[^A-ZА-ЯЁ-]",
		"",
		value,
	)


def _action_mask(panel_frame):
	hsv = cv2.cvtColor(
		panel_frame,
		cv2.COLOR_BGR2HSV,
	)

	return cv2.inRange(
		hsv,
		np.array([0, 115, 95], dtype=np.uint8),
		np.array([179, 255, 255], dtype=np.uint8),
	)


def _action_roi(panel_frame):
	height, width = panel_frame.shape[:2]

	# Иконки статуса выступают слева от текста.
	# Их полностью исключаем из action ROI.
	return panel_frame[
		0:int(height * 0.60),
		int(width * 0.22):int(width * 0.98),
	]


def has_colored_action(panel_frame):
	if panel_frame.size == 0:
		return False

	roi = _action_roi(
		panel_frame
	)

	if roi.size == 0:
		return False

	mask = _action_mask(
		roi
	)

	contours, _ = cv2.findContours(
		mask,
		cv2.RETR_EXTERNAL,
		cv2.CHAIN_APPROX_SIMPLE,
	)

	if not contours:
		return False

	points = np.vstack(contours)
	x, y, width, height = cv2.boundingRect(
		points
	)

	roi_height, roi_width = roi.shape[:2]

	# Действие — строка текста, а не одиночная цветная иконка.
	if width < roi_width * 0.34:
		return False

	if height < roi_height * 0.18:
		return False

	colored = cv2.countNonZero(
		mask
	)

	return colored >= max(
		18,
		int(roi_width * roi_height * 0.018),
	)


def read_player_action(panel_frame):
	if not has_colored_action(
		panel_frame
	):
		return None

	roi = _action_roi(
		panel_frame
	)

	mask = _action_mask(
		roi
	)

	mask = cv2.resize(
		mask,
		None,
		fx=3.0,
		fy=3.0,
		interpolation=cv2.INTER_CUBIC,
	)

	text = pytesseract.image_to_string(
		mask,
		lang="rus+eng",
		config="--psm 7",
	)

	normalized = _normalize_text(
		text
	)

	for label, action in ACTION_ALIASES.items():
		if label in normalized:
			return action

	# Не превращаем непонятный цветной текст в ник,
	# но и не спамим unknown от каждой статусной иконки.
	if len(normalized) >= 4:
		return "unknown"

	return None
