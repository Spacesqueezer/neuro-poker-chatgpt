from pathlib import Path

import cv2
import pytesseract
import re

from poker.vision.detection.cards import crop_card
from poker.vision.project_paths import find_project_root
from poker.vision.recognition.card_features import (
	rank_feature,
	similarity,
	suit_feature,
)


VALID_RANKS = set(
	"AKQJT98765432"
)


class CardRecognizer:
	def __init__(
		self,
		template_threshold=0.73,
	):
		self.template_threshold = template_threshold

		root = find_project_root()

		self.template_root = (
			root
			/ "assets"
			/ "cards"
			/ "templates"
		)

		self.rank_templates = self._load_templates(
			self.template_root / "ranks"
		)

		self.suit_templates = self._load_templates(
			self.template_root / "suits"
		)

		print(
			f"[CARDS] Templates: "
			f"ranks={sum(map(len, self.rank_templates.values()))} "
			f"suits={sum(map(len, self.suit_templates.values()))}"
		)

	def recognize_many(
		self,
		frame,
		cards,
	):
		return [
			self.recognize(
				crop_card(
					frame,
					card,
				)
			)
			for card in cards
		]

	def recognize(
		self,
		card_frame,
	):
		if card_frame.size == 0:
			return "??"

		rank, rank_score = self._template_match(
			rank_feature(
				card_frame
			),
			self.rank_templates,
		)

		suit, suit_score = self._template_match(
			suit_feature(
				card_frame
			),
			self.suit_templates,
		)

		if (
			not rank
			or rank_score < self.template_threshold
		):
			rank = self._ocr_rank(
				card_frame
			)

		if (
			not suit
			or suit_score < self.template_threshold
		):
			# Для статистики/игрового state лучше неизвестная масть, чем
			# уверенно неверная. Распознаём suit только по отдельному
			# suit_feature и накопленным шаблонам.
			suit = ""

		return (
			f"{rank or '?'}"
			f"{suit or '?'}"
		)

	def _load_templates(
		self,
		folder,
	):
		result = {}

		if not folder.exists():
			return result

		for label_folder in folder.iterdir():
			if not label_folder.is_dir():
				continue

			label = label_folder.name

			for path in label_folder.glob("*.png"):
				image = cv2.imread(
					str(path),
					cv2.IMREAD_GRAYSCALE,
				)

				if image is None:
					continue

				result.setdefault(
					label,
					[],
				).append(image)

		return result

	def _template_match(
		self,
		feature,
		templates,
	):
		if feature is None or not templates:
			return "", 0.0

		best_label = ""
		best_score = 0.0

		for label, samples in templates.items():
			for sample in samples:
				score = similarity(
					feature,
					sample,
				)

				if score > best_score:
					best_label = label
					best_score = score

		return best_label, best_score

	def _ocr_rank(
		self,
		card_frame,
	):
		height, width = card_frame.shape[:2]

		corner = card_frame[
			int(height * 0.05):int(height * 0.43),
			int(width * 0.07):int(width * 0.43),
		]

		gray = cv2.cvtColor(
			corner,
			cv2.COLOR_BGR2GRAY,
		)

		gray = cv2.resize(
			gray,
			None,
			fx=3.0,
			fy=3.0,
			interpolation=cv2.INTER_CUBIC,
		)

		_, threshold = cv2.threshold(
			gray,
			175,
			255,
			cv2.THRESH_BINARY_INV,
		)

		text = pytesseract.image_to_string(
			threshold,
			lang="eng",
			config=(
				"--psm 10 "
				"-c tessedit_char_whitelist="
				"AKQJ1098765432"
			),
		)

		text = re.sub(
			r"[^AKQJ0-9]",
			"",
			text.upper(),
		)

		if text in ("10", "0"):
			return "T"

		if text and text[0] in VALID_RANKS:
			return text[0]

		return ""

	def _heuristic_suit(
		self,
		card_frame,
	):
		# Fallback оставляем только до накопления шаблонов.
		# После появления базы эта ветка практически не используется.
		height, width = card_frame.shape[:2]

		roi = card_frame[
			int(height * 0.23):int(height * 0.62),
			0:int(width * 0.58),
		]

		if roi.size == 0:
			return ""

		hsv = cv2.cvtColor(
			roi,
			cv2.COLOR_BGR2HSV,
		)

		red_1 = cv2.inRange(
			hsv,
			(0, 70, 70),
			(12, 255, 255),
		)

		red_2 = cv2.inRange(
			hsv,
			(165, 70, 70),
			(179, 255, 255),
		)

		red = cv2.bitwise_or(
			red_1,
			red_2,
		)

		if cv2.countNonZero(red) > 20:
			# Пока шаблона нет, red suit неизвестен точнее.
			return "?"

		return "?"
