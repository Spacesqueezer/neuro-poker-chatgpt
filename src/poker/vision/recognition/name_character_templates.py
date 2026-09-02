from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib

import cv2
import numpy as np

from poker.vision.recognition.name_width_model import (
	WidthModel,
	expected_boundaries,
	load_width_model,
	update_width_model,
)


VALID_NAME_CHARS = (
	"abcdefghijklmnopqrstuvwxyz"
	"ABCDEFGHIJKLMNOPQRSTUVWXYZ"
	"0123456789_-"
)


@dataclass(frozen=True)
class SegmentedName:
	segments: list[np.ndarray]
	bounds: list[tuple[int, int]]
	normalized: np.ndarray


def normalize_name_crop(image):
	if image is None or image.size == 0:
		return None

	gray = cv2.cvtColor(
		image,
		cv2.COLOR_BGR2GRAY,
	)

	gray = cv2.GaussianBlur(
		gray,
		(3, 3),
		0,
	)

	_, binary = cv2.threshold(
		gray,
		0,
		255,
		cv2.THRESH_BINARY + cv2.THRESH_OTSU,
	)

	white_ratio = (
		cv2.countNonZero(binary)
		/ float(binary.shape[0] * binary.shape[1])
	)

	if white_ratio > 0.55:
		binary = cv2.bitwise_not(
			binary
		)

	binary = _crop_to_ink(
		binary
	)

	if binary is None:
		return None

	return binary


def segment_known_name(
	project_root: Path,
	image,
	label: str,
) -> SegmentedName | None:
	if not label:
		return None

	binary = normalize_name_crop(
		image
	)

	if binary is None:
		return None

	if binary.shape[1] < len(label) * 2:
		return None

	model = load_width_model(
		project_root
	)

	projection = np.count_nonzero(
		binary,
		axis=0,
	).astype(np.float32)

	expected = expected_boundaries(
		label,
		model,
		binary.shape[1],
	)

	cuts = _find_global_cuts(
		projection,
		label,
		model,
		expected,
	)

	if len(cuts) != len(label) - 1:
		return None

	raw_bounds = [
		0,
		*cuts,
		binary.shape[1],
	]

	segments = []
	bounds = []

	for index in range(len(label)):
		x1 = raw_bounds[index]
		x2 = raw_bounds[index + 1]

		char_image = binary[
			:,
			x1:x2,
		]

		# Не режем символ по вертикали: для '_' и '-' именно вертикальная
		# позиция отличает baseline от средней линии.
		horizontal = _crop_horizontal_to_ink(
			char_image
		)

		if horizontal is None:
			return None

		segments.append(
			normalize_character_image(
				horizontal
			)
		)

		bounds.append(
			(x1, x2)
		)

	return SegmentedName(
		segments=segments,
		bounds=bounds,
		normalized=binary,
	)


def normalize_character_image(
	char_image,
	shape=(28, 40),
):
	canvas = np.zeros(
		(shape[1], shape[0]),
		dtype=np.uint8,
	)

	height, width = char_image.shape[:2]

	if height <= 0 or width <= 0:
		return canvas

	scale = min(
		(shape[0] - 4) / max(width, 1),
		(shape[1] - 4) / max(height, 1),
	)

	new_width = max(
		1,
		int(round(width * scale)),
	)

	new_height = max(
		1,
		int(round(height * scale)),
	)

	resized = cv2.resize(
		char_image,
		(new_width, new_height),
		interpolation=cv2.INTER_AREA,
	)

	offset_x = (
		shape[0] - new_width
	) // 2

	offset_y = (
		shape[1] - new_height
	) // 2

	canvas[
		offset_y:offset_y + new_height,
		offset_x:offset_x + new_width,
	] = resized

	return canvas


def save_character_template(
	project_root,
	character,
	image,
):
	if character not in VALID_NAME_CHARS:
		raise ValueError(
			f"Unsupported character: {character}"
		)

	template_root = (
		project_root
		/ "assets"
		/ "players"
		/ "templates"
		/ "chars"
		/ character
	)

	template_root.mkdir(
		parents=True,
		exist_ok=True,
	)

	output = (
		template_root
		/ f"{_image_hash(image)}.png"
	)

	if not output.exists():
		cv2.imwrite(
			str(output),
			image,
		)

	return output


def save_name_template(
	project_root,
	name,
	image,
):
	if not name:
		return None

	if any(
		character not in VALID_NAME_CHARS
		for character in name
	):
		raise ValueError(
			"Nickname contains unsupported characters"
		)

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

	target_width = max(
		1,
		int(
			round(
				binary.shape[1]
				* scale
			)
		),
	)

	normalized = cv2.resize(
		binary,
		(target_width, target_height),
		interpolation=cv2.INTER_AREA,
	)

	template_root = (
		project_root
		/ "assets"
		/ "players"
		/ "templates"
		/ "names"
		/ name
	)

	template_root.mkdir(
		parents=True,
		exist_ok=True,
	)

	output = (
		template_root
		/ f"{_image_hash(normalized)}.png"
	)

	if not output.exists():
		cv2.imwrite(
			str(output),
			normalized,
		)

	return output


def accept_segmented_sample(
	project_root: Path,
	label: str,
	segmented: SegmentedName,
):
	if len(label) != len(segmented.segments):
		raise ValueError(
			"Label and segment count mismatch"
		)

	widths = []

	for character, segment, bound in zip(
		label,
		segmented.segments,
		segmented.bounds,
	):
		save_character_template(
			project_root,
			character,
			segment,
		)

		widths.append(
			bound[1] - bound[0]
		)

	update_width_model(
		project_root,
		label,
		widths,
	)


def _find_global_cuts(
	projection,
	label,
	model: WidthModel,
	expected,
):
	width = len(projection)
	char_count = len(label)

	if char_count <= 1:
		return []

	expected_positions = [
		0.0,
		*expected,
		float(width),
	]

	inf = float("inf")

	dp = [
		np.full(
			width + 1,
			inf,
			dtype=np.float64,
		)
		for _ in range(char_count + 1)
	]

	parent = [
		np.full(
			width + 1,
			-1,
			dtype=np.int32,
		)
		for _ in range(char_count + 1)
	]

	dp[0][0] = 0.0

	for k in range(
		1,
		char_count + 1,
	):
		expected_left = expected_positions[k - 1]
		expected_right = expected_positions[k]
		expected_width = max(
			expected_right - expected_left,
			2.0,
		)

		min_cell = max(
			2,
			int(
				expected_width * 0.50
			),
		)

		max_cell = max(
			min_cell + 1,
			int(
				expected_width * 1.75
			),
		)

		expected_x = expected_right

		if k == char_count:
			x_values = [width]
		else:
			radius = max(
				3,
				int(
					expected_width * 0.70
				),
			)

			x_values = range(
				max(
					1,
					int(
						expected_x - radius
					),
				),
				min(
					width - 1,
					int(
						expected_x + radius
					),
				) + 1,
			)

		for x in x_values:
			prev_min = max(
				0,
				x - max_cell,
			)

			prev_max = x - min_cell

			if prev_max < prev_min:
				continue

			best_cost = inf
			best_prev = -1

			for prev in range(
				prev_min,
				prev_max + 1,
			):
				base = dp[k - 1][prev]

				if not np.isfinite(base):
					continue

				cell_width = x - prev

				width_cost = (
					(cell_width - expected_width)
					/ expected_width
				) ** 2 * 6.0

				position_cost = (
					(x - expected_x)
					/ max(
						expected_width,
						1.0,
					)
				) ** 2 * 2.5

				cut_cost = 0.0

				if x < width:
					left = max(
						0,
						x - 1,
					)

					right = min(
						width,
						x + 2,
					)

					cut_cost = float(
						np.mean(
							projection[
								left:right
							]
						)
					) * 0.42

				cost = (
					base
					+ width_cost
					+ position_cost
					+ cut_cost
				)

				if cost < best_cost:
					best_cost = cost
					best_prev = prev

			if best_prev >= 0:
				dp[k][x] = best_cost
				parent[k][x] = best_prev

	if not np.isfinite(
		dp[char_count][width]
	):
		return []

	cuts = []
	x = width

	for k in range(
		char_count,
		0,
		-1,
	):
		prev = int(
			parent[k][x]
		)

		if prev < 0:
			return []

		if k > 1:
			cuts.append(
				prev
			)

		x = prev

	cuts.reverse()

	return cuts


def _crop_horizontal_to_ink(binary):
	points = cv2.findNonZero(
		binary
	)

	if points is None:
		return None

	x, _, width, _ = cv2.boundingRect(
		points
	)

	if width <= 0:
		return None

	return binary[
		:,
		x:x + width,
	]


def _crop_to_ink(binary):
	points = cv2.findNonZero(
		binary
	)

	if points is None:
		return None

	x, y, width, height = cv2.boundingRect(
		points
	)

	if width <= 0 or height <= 0:
		return None

	return binary[
		y:y + height,
		x:x + width,
	]


def _image_hash(image):
	ok, encoded = cv2.imencode(
		".png",
		image,
	)

	if not ok:
		raise RuntimeError(
			"Could not encode image"
		)

	return hashlib.sha1(
		encoded.tobytes()
	).hexdigest()[:12]
