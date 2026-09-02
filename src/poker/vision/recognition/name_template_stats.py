from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math

import cv2
import numpy as np

from poker.vision.recognition.name_character_templates import (
	VALID_NAME_CHARS,
	normalize_character_image,
	normalize_name_crop,
)


@dataclass(frozen=True)
class CharacterStats:
	character: str
	sample_count: int
	readiness: float
	cohesion: float
	separation: float


@dataclass(frozen=True)
class CharacterPrediction:
	character: str | None
	confidence: float
	margin: float
	second_character: str | None


@dataclass(frozen=True)
class NameSuggestion:
	name: str | None
	confidence: float
	margin: float
	source: str


def _binary(image):
	if image is None:
		return None

	if len(image.shape) == 3:
		image = cv2.cvtColor(
			image,
			cv2.COLOR_BGR2GRAY,
		)

	_, image = cv2.threshold(
		image,
		127,
		255,
		cv2.THRESH_BINARY,
	)

	return image


def _shifted_similarity(left, right, radius=2):
	left = _binary(left)
	right = _binary(right)

	if left is None or right is None:
		return 0.0

	if left.shape != right.shape:
		right = cv2.resize(
			right,
			(left.shape[1], left.shape[0]),
			interpolation=cv2.INTER_AREA,
		)

	best = 0.0

	for dy in range(-radius, radius + 1):
		for dx in range(-radius, radius + 1):
			matrix = np.float32(
				[
					[1, 0, dx],
					[0, 1, dy],
				]
			)

			shifted = cv2.warpAffine(
				right,
				matrix,
				(left.shape[1], left.shape[0]),
				flags=cv2.INTER_NEAREST,
				borderMode=cv2.BORDER_CONSTANT,
				borderValue=0,
			)

			diff = cv2.absdiff(
				left,
				shifted,
			)

			similarity = max(
				0.0,
				1.0
				- float(
					np.mean(diff)
				) / 255.0,
			)

			if similarity > best:
				best = similarity

	return best


def load_character_templates(project_root: Path):
	root = (
		project_root
		/ "assets"
		/ "players"
		/ "templates"
		/ "chars"
	)

	result = {}

	if not root.exists():
		return result

	for folder in root.iterdir():
		if not folder.is_dir():
			continue

		character = folder.name

		if len(character) != 1:
			continue

		samples = []

		for path in folder.glob("*.png"):
			image = cv2.imread(
				str(path),
				cv2.IMREAD_GRAYSCALE,
			)

			if image is None:
				continue

			if image.shape != (40, 28):
				image = normalize_character_image(
					image
				)

			samples.append(
				_binary(image)
			)

		if samples:
			result[character] = samples

	return result


def predict_character(
	segment,
	templates,
):
	if segment is None:
		return CharacterPrediction(
			character=None,
			confidence=0.0,
			margin=0.0,
			second_character=None,
		)

	scores = []

	for character, samples in templates.items():
		if not samples:
			continue

		best = max(
			_shifted_similarity(
				segment,
				sample,
			)
			for sample in samples
		)

		scores.append(
			(
				best,
				character,
			)
		)

	if not scores:
		return CharacterPrediction(
			character=None,
			confidence=0.0,
			margin=0.0,
			second_character=None,
		)

	scores.sort(
		reverse=True,
		key=lambda item: item[0],
	)

	best_score, best_character = scores[0]

	if len(scores) > 1:
		second_score, second_character = scores[1]
	else:
		second_score = 0.0
		second_character = None

	return CharacterPrediction(
		character=best_character,
		confidence=float(best_score),
		margin=float(
			best_score - second_score
		),
		second_character=second_character,
	)


def compute_character_stats(
	project_root: Path,
):
	templates = load_character_templates(
		project_root
	)

	medoids = {}

	for character, samples in templates.items():
		if not samples:
			continue

		if len(samples) == 1:
			medoids[character] = samples[0]
			continue

		best_index = 0
		best_score = -1.0

		for index, candidate in enumerate(samples):
			score = 0.0

			for other in samples:
				score += _shifted_similarity(
					candidate,
					other,
					radius=1,
				)

			score /= len(samples)

			if score > best_score:
				best_score = score
				best_index = index

		medoids[character] = samples[
			best_index
		]

	result = {}

	for character in VALID_NAME_CHARS:
		samples = templates.get(
			character,
			[],
		)

		count = len(samples)

		if count == 0:
			result[character] = CharacterStats(
				character=character,
				sample_count=0,
				readiness=0.0,
				cohesion=0.0,
				separation=0.0,
			)
			continue

		medoid = medoids[
			character
		]

		cohesion = sum(
			_shifted_similarity(
				medoid,
				sample,
				radius=1,
			)
			for sample in samples
		) / len(samples)

		cross_scores = []

		for other_character, other_medoid in medoids.items():
			if other_character == character:
				continue

			cross_scores.append(
				_shifted_similarity(
					medoid,
					other_medoid,
					radius=1,
				)
			)

		if cross_scores:
			nearest_other = max(
				cross_scores
			)
		else:
			nearest_other = 0.0

		separation = max(
			0.0,
			1.0 - nearest_other,
		)

		coverage = min(
			1.0,
			count / 6.0,
		)

		readiness = (
			coverage * 0.45
			+ cohesion * 0.35
			+ separation * 0.20
		)

		result[character] = CharacterStats(
			character=character,
			sample_count=count,
			readiness=float(
				max(
					0.0,
					min(
						1.0,
						readiness,
					),
				)
			),
			cohesion=float(cohesion),
			separation=float(separation),
		)

	return result


def dataset_summary(
	stats,
):
	if not stats:
		return {
			"global_readiness": 0.0,
			"covered": 0,
			"total": len(
				VALID_NAME_CHARS
			),
			"samples": 0,
		}

	values = list(
		stats.values()
	)

	covered = sum(
		1
		for item in values
		if item.sample_count > 0
	)

	samples = sum(
		item.sample_count
		for item in values
	)

	global_readiness = sum(
		item.readiness
		for item in values
	) / len(values)

	return {
		"global_readiness": float(
			global_readiness
		),
		"covered": covered,
		"total": len(values),
		"samples": samples,
	}


def _normalize_name_template(image):
	binary = normalize_name_crop(
		image
	)

	if binary is None:
		return None

	target_height = 42

	scale = (
		target_height
		/ max(
			binary.shape[0],
			1,
		)
	)

	width = max(
		1,
		int(
			round(
				binary.shape[1]
				* scale
			)
		),
	)

	return cv2.resize(
		binary,
		(width, target_height),
		interpolation=cv2.INTER_AREA,
	)


def suggest_known_name(
	project_root: Path,
	image,
):
	candidate = _normalize_name_template(
		image
	)

	if candidate is None:
		return NameSuggestion(
			name=None,
			confidence=0.0,
			margin=0.0,
			source="none",
		)

	root = (
		project_root
		/ "assets"
		/ "players"
		/ "templates"
		/ "names"
	)

	if not root.exists():
		return NameSuggestion(
			name=None,
			confidence=0.0,
			margin=0.0,
			source="none",
		)

	scores = []

	for folder in root.iterdir():
		if not folder.is_dir():
			continue

		best = 0.0

		for path in folder.glob("*.png"):
			template = cv2.imread(
				str(path),
				cv2.IMREAD_GRAYSCALE,
			)

			if template is None:
				continue

			width_ratio = min(
				candidate.shape[1],
				template.shape[1],
			) / max(
				candidate.shape[1],
				template.shape[1],
			)

			resized = cv2.resize(
				candidate,
				(
					template.shape[1],
					template.shape[0],
				),
				interpolation=cv2.INTER_AREA,
			)

			pixel_score = _shifted_similarity(
				resized,
				template,
				radius=1,
			)

			score = (
				pixel_score * 0.82
				+ width_ratio * 0.18
			)

			if score > best:
				best = score

		if best > 0.0:
			scores.append(
				(
					best,
					folder.name,
				)
			)

	if not scores:
		return NameSuggestion(
			name=None,
			confidence=0.0,
			margin=0.0,
			source="none",
		)

	scores.sort(
		reverse=True,
		key=lambda item: item[0],
	)

	best_score, best_name = scores[0]

	if len(scores) > 1:
		second_score = scores[1][0]
	else:
		second_score = 0.0

	margin = best_score - second_score

	# Уверенность deliberately conservative: похожий полный шаблон
	# не должен автоматически становиться истиной.
	confidence = max(
		0.0,
		min(
			1.0,
			(best_score - 0.45) / 0.45,
		),
	)

	return NameSuggestion(
		name=best_name,
		confidence=float(confidence),
		margin=float(margin),
		source="full-name templates",
	)
