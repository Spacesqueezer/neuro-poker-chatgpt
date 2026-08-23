import os
import re

import cv2
import pytesseract


pytesseract.pytesseract.tesseract_cmd = (
	"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
)

os.environ["TESSDATA_PREFIX"] = (
	"C:\\Program Files\\Tesseract-OCR\\tessdata"
)


ACTION_WORDS = [
	"СБРАСЫВАЕТ",
	"УРАВНИВАЕТ",
	"ЧЕК",
	"ФОЛД",
	"ПОДНЯТЬ",
	"ПОДНИМАЕТ",
	"CHECK",
	"FOLD",
	"CALL",
	"RAISE",
]


def _preprocess(image):
	gray = cv2.cvtColor(
		image,
		cv2.COLOR_BGR2GRAY,
	)

	gray = cv2.resize(
		gray,
		None,
		fx=3.0,
		fy=3.0,
		interpolation=cv2.INTER_CUBIC,
	)

	gray = cv2.GaussianBlur(
		gray,
		(3, 3),
		0,
	)

	_, thresh = cv2.threshold(
		gray,
		0,
		255,
		cv2.THRESH_BINARY + cv2.THRESH_OTSU,
	)

	return thresh


def _cleanup(text):
	text = text.strip()
	text = re.sub(r"\s+", " ", text)

	text = re.sub(
		r"[^A-Za-z0-9_\-#]",
		"",
		text,
	)

	if not text:
		return ""

	if text.upper() in ACTION_WORDS:
		return ""

	return text


def read_player_name(image):
	try:
		prepared = _preprocess(image)

		config = (
			"--psm 7 "
			"--oem 3 "
			"-c tessedit_char_whitelist="
			"ABCDEFGHIJKLMNOPQRSTUVWXYZ"
			"abcdefghijklmnopqrstuvwxyz"
			"0123456789_-#"
		)

		text = pytesseract.image_to_string(
			prepared,
			lang="eng",
			config=config,
		)

		return _cleanup(text)

	except Exception as error:
		print(f"[OCR ERROR] {error}")
		return ""
