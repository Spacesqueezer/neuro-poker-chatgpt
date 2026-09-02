import cv2
import numpy as np
import pytesseract

from poker.vision.ocr.tesseract_runtime import TESSERACT_RUNTIME


def _ocr(image):
	return pytesseract.image_to_string(
		image,
		lang="eng",
		config=(
			"--psm 7 "
			"-c tessedit_char_whitelist="
			"abcdefghijklmnopqrstuvwxyz"
			"ABCDEFGHIJKLMNOPQRSTUVWXYZ"
			"0123456789_-"
		),
	).strip()


def read_player_name(image):
	if image is None or image.size == 0:
		return ""

	gray = cv2.cvtColor(
		image,
		cv2.COLOR_BGR2GRAY,
	)

	upscaled = cv2.resize(
		gray,
		None,
		fx=3.0,
		fy=3.0,
		interpolation=cv2.INTER_CUBIC,
	)

	# Белые ники и серые ники неактивных игроков читаем отдельно.
	# Потом выбираем более содержательный результат.
	_, light = cv2.threshold(
		upscaled,
		145,
		255,
		cv2.THRESH_BINARY,
	)

	_, gray_name = cv2.threshold(
		upscaled,
		82,
		255,
		cv2.THRESH_BINARY,
	)

	candidates = [
		_ocr(light),
		_ocr(gray_name),
		_ocr(upscaled),
	]

	candidates = [
		value
		for value in candidates
		if value
	]

	if not candidates:
		return ""

	# Обычно корректный ник длиннее случайного OCR-мусора.
	return max(
		candidates,
		key=lambda value: (
			sum(ch.isalnum() for ch in value),
			len(value),
		),
	)
