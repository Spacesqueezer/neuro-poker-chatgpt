import re
from dataclasses import dataclass

import cv2
import numpy as np
import pytesseract
from pytesseract import Output

from poker.vision.ocr.tesseract_runtime import TESSERACT_RUNTIME
from poker.vision.project_paths import find_project_root
from poker.vision.recognition.name_character_templates import (
	segment_known_name,
)
from poker.vision.recognition.name_template_predictor import (
	CharacterTemplatePredictor,
)


HIGH_TEMPLATE_SCORE = 0.82
MEDIUM_TEMPLATE_SCORE = 0.78
MIN_TEMPLATE_MARGIN = 0.018
MIN_ACCEPT_OCR_CONFIDENCE = 25.0

_TEMPLATE_PREDICTOR = None


@dataclass(frozen=True)
class NameCandidate:
	value: str
	ocr_confidence: float
	template_score: float
	template_margin: float
	template_agreement: float
	combined_score: float


def _get_template_predictor():
	global _TEMPLATE_PREDICTOR

	if _TEMPLATE_PREDICTOR is None:
		try:
			_TEMPLATE_PREDICTOR = (
				CharacterTemplatePredictor(
					find_project_root()
				)
			)
		except Exception:
			return None

	return _TEMPLATE_PREDICTOR


def _normalize_candidate(
	value,
):
	if not value:
		return ""

	value = (
		value
		.strip()
		.lower()
	)

	value = re.sub(
		r"[^a-z0-9_]",
		"",
		value,
	)

	return value


def _ocr_hidden_marker(
	image,
):
	if (
		image is None
		or image.size == 0
	):
		return ""

	try:
		value = pytesseract.image_to_string(
			image,
			lang="eng",
			config=(
				"--psm 7 "
				"-c tessedit_char_whitelist=*"
			),
		).strip()
	except Exception:
		return ""

	if value.count("*") >= 4:
		return "*****"

	return ""


def _ocr_tokens(
	image,
):
	if (
		image is None
		or image.size == 0
	):
		return []

	try:
		data = pytesseract.image_to_data(
			image,
			lang="eng",
			config=(
				"--psm 7 "
				"-c preserve_interword_spaces=1 "
				"-c tessedit_char_whitelist="
				"abcdefghijklmnopqrstuvwxyz"
				"ABCDEFGHIJKLMNOPQRSTUVWXYZ"
				"0123456789_"
			),
			output_type=Output.DICT,
		)
	except Exception:
		return []

	result = []

	for raw_text, raw_confidence in zip(
		data.get(
			"text",
			[],
		),
		data.get(
			"conf",
			[],
		),
	):
		value = _normalize_candidate(
			raw_text
		)

		if len(value) < 3:
			continue

		try:
			confidence = float(
				raw_confidence
			)
		except (
			TypeError,
			ValueError,
		):
			confidence = -1.0

		if confidence < 0.0:
			continue

		result.append(
			(
				value,
				confidence,
			)
		)

	return result


def _template_verify(
	image,
	ocr_value,
):
	predictor = (
		_get_template_predictor()
	)

	if (
		predictor is None
		or not predictor.templates
	):
		return (
			ocr_value,
			0.0,
			0.0,
			0.0,
		)

	try:
		segmented = segment_known_name(
			find_project_root(),
			image,
			ocr_value,
		)
	except Exception:
		segmented = None

	if (
		segmented is None
		or len(
			segmented.segments
		) != len(
			ocr_value
		)
	):
		return (
			ocr_value,
			0.0,
			0.0,
			0.0,
		)

	corrected = []
	scores = []
	margins = []
	agreements = 0

	for ocr_character, segment in zip(
		ocr_value,
		segmented.segments,
	):
		top = predictor.predict_top(
			segment,
			limit=2,
		)

		if not top:
			corrected.append(
				ocr_character
			)
			continue

		best_character, best_score = (
			top[0]
		)

		second_score = (
			top[1][1]
			if len(top) >= 2
			else 0.0
		)

		margin = max(
			0.0,
			best_score
			- second_score,
		)

		scores.append(
			best_score
		)

		margins.append(
			margin
		)

		if best_character == ocr_character:
			agreements += 1
			corrected.append(
				ocr_character
			)

			continue

		# Template wins only if it is actually convincing.
		# A raw nearest-template guess without a margin is not enough.
		replace = (
			(
				best_score
				>= HIGH_TEMPLATE_SCORE
				and margin
				>= MIN_TEMPLATE_MARGIN
			)
			or (
				best_score
				>= MEDIUM_TEMPLATE_SCORE
				and margin
				>= 0.032
			)
		)

		corrected.append(
			best_character
			if replace
			else ocr_character
		)

	if not scores:
		return (
			ocr_value,
			0.0,
			0.0,
			0.0,
		)

	return (
		"".join(
			corrected
		),
		float(
			np.mean(
				scores
			)
		),
		float(
			np.mean(
				margins
			)
		),
		float(
			agreements
			/ max(
				len(
					ocr_value
				),
				1,
			)
		),
	)


def _build_candidate(
	image,
	value,
	ocr_confidence,
):
	(
		corrected,
		template_score,
		template_margin,
		template_agreement,
	) = _template_verify(
		image,
		value,
	)

	# OCR confidence remains important, but it is no longer the only judge.
	# The fixed PokerDom font gives our own character templates a strong vote.
	combined = (
		ocr_confidence * 0.48
		+ template_score * 100.0 * 0.37
		+ template_agreement * 100.0 * 0.10
		+ min(
			template_margin,
			0.10,
		) * 100.0 * 0.05
	)

	return NameCandidate(
		value=corrected,
		ocr_confidence=float(
			ocr_confidence
		),
		template_score=template_score,
		template_margin=template_margin,
		template_agreement=template_agreement,
		combined_score=float(
			combined
		),
	)


def _deduplicate_candidates(
	candidates,
):
	best = {}

	for candidate in candidates:
		previous = best.get(
			candidate.value
		)

		if (
			previous is None
			or candidate.combined_score
			> previous.combined_score
		):
			best[
				candidate.value
			] = candidate

	return list(
		best.values()
	)


def read_player_name(
	image,
):
	if (
		image is None
		or image.size == 0
	):
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

	for hidden_image in (
		light,
		gray_name,
	):
		if (
			_ocr_hidden_marker(
				hidden_image
			)
			== "*****"
		):
			return "*****"

	# Tesseract proposes candidate strings and lengths.
	# Character templates then verify / repair those strings.
	variants = (
		image,
		cv2.cvtColor(
			light,
			cv2.COLOR_GRAY2BGR,
		),
		cv2.cvtColor(
			gray_name,
			cv2.COLOR_GRAY2BGR,
		),
	)

	ocr_variants = (
		upscaled,
		light,
		gray_name,
	)

	candidates = []

	for (
		source_image,
		ocr_image,
	) in zip(
		variants,
		ocr_variants,
	):
		for (
			value,
			confidence,
		) in _ocr_tokens(
			ocr_image
		):
			if (
				confidence
				< MIN_ACCEPT_OCR_CONFIDENCE
			):
				continue

			candidates.append(
				_build_candidate(
					source_image,
					value,
					confidence,
				)
			)

	candidates = (
		_deduplicate_candidates(
			candidates
		)
	)

	if not candidates:
		return ""

	candidates.sort(
		key=lambda item: (
			item.combined_score,
			item.template_score,
			item.ocr_confidence,
		),
		reverse=True,
	)

	return candidates[0].value
