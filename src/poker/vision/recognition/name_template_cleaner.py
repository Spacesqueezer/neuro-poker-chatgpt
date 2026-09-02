from __future__ import annotations

from dataclasses import dataclass
import shutil

import cv2
import numpy as np


@dataclass(frozen=True)
class CleanupResult:
	cleaned: np.ndarray | None
	rejected: bool
	reason: str
	kept_components: int
	removed_components: int


def clean_character_template(image):
	if image is None or image.size == 0:
		return CleanupResult(None, True, "empty image", 0, 0)

	if len(image.shape) == 3:
		gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
	else:
		gray = image.copy()

	_, binary = cv2.threshold(
		gray,
		127,
		255,
		cv2.THRESH_BINARY,
	)

	contours, _ = cv2.findContours(
		binary,
		cv2.RETR_EXTERNAL,
		cv2.CHAIN_APPROX_SIMPLE,
	)

	if not contours:
		return CleanupResult(None, True, "no components", 0, 0)

	components = []

	for contour in contours:
		x, y, width, height = cv2.boundingRect(contour)
		area = cv2.contourArea(contour)

		components.append(
			{
				"contour": contour,
				"x": x,
				"y": y,
				"width": width,
				"height": height,
				"area": area,
			}
		)

	components.sort(
		key=lambda item: item["area"],
		reverse=True,
	)

	main = components[0]

	if main["area"] < 8:
		return CleanupResult(
			None,
			True,
			"main component too small",
			0,
			len(components),
		)

	image_height, image_width = binary.shape[:2]
	keep = [main]
	removed = 0

	for component in components[1:]:
		if _belongs_to_main(
			component,
			main,
			image_width,
			image_height,
		):
			keep.append(component)
		else:
			removed += 1

	mask = np.zeros_like(binary)

	for component in keep:
		cv2.drawContours(
			mask,
			[component["contour"]],
			-1,
			255,
			thickness=cv2.FILLED,
		)

	points = cv2.findNonZero(mask)

	if points is None:
		return CleanupResult(
			None,
			True,
			"all components removed",
			0,
			len(components),
		)

	x, y, crop_width, crop_height = cv2.boundingRect(points)

	cleaned = mask[
		y:y + crop_height,
		x:x + crop_width,
	]

	cleaned = _normalize(cleaned)

	return CleanupResult(
		cleaned=cleaned,
		rejected=False,
		reason="ok",
		kept_components=len(keep),
		removed_components=removed,
	)


def _belongs_to_main(
	component,
	main,
	image_width,
	image_height,
):
	area_ratio = (
		component["area"]
		/ max(main["area"], 1.0)
	)

	if area_ratio < 0.015:
		return False

	main_center_x = main["x"] + main["width"] / 2
	main_center_y = main["y"] + main["height"] / 2

	center_x = component["x"] + component["width"] / 2
	center_y = component["y"] + component["height"] / 2

	dx = abs(center_x - main_center_x)
	dy = abs(center_y - main_center_y)

	horizontal_limit = max(
		main["width"] * 0.70,
		image_width * 0.18,
	)

	vertical_limit = max(
		main["height"] * 0.90,
		image_height * 0.25,
	)

	# Точка i/j и другие мелкие части, реально относящиеся к глифу.
	if (
		dx <= horizontal_limit
		and dy <= vertical_limit
	):
		return True

	left = max(component["x"], main["x"])
	right = min(
		component["x"] + component["width"],
		main["x"] + main["width"],
	)

	overlap = max(0, right - left)

	if overlap > 0:
		overlap_ratio = (
			overlap
			/ max(
				min(
					component["width"],
					main["width"],
				),
				1,
			)
		)

		if (
			overlap_ratio >= 0.35
			and area_ratio >= 0.03
		):
			return True

	return False


def _normalize(image, shape=(28, 40)):
	canvas = np.zeros(
		(shape[1], shape[0]),
		dtype=np.uint8,
	)

	height, width = image.shape[:2]

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
		image,
		(new_width, new_height),
		interpolation=cv2.INTER_AREA,
	)

	offset_x = (shape[0] - new_width) // 2
	offset_y = (shape[1] - new_height) // 2

	canvas[
		offset_y:offset_y + new_height,
		offset_x:offset_x + new_width,
	] = resized

	return canvas


def clean_template_tree(
	project_root,
	dry_run=False,
):
	template_root = (
		project_root
		/ "assets"
		/ "players"
		/ "templates"
		/ "chars"
	)

	rejected_root = (
		project_root
		/ "assets"
		/ "players"
		/ "templates"
		/ "rejected"
	)

	stats = {
		"processed": 0,
		"cleaned": 0,
		"rejected": 0,
		"unchanged": 0,
	}

	if not template_root.exists():
		return stats

	for path in sorted(
		template_root.glob("*/*.png")
	):
		stats["processed"] += 1

		image = cv2.imread(
			str(path),
			cv2.IMREAD_GRAYSCALE,
		)

		result = clean_character_template(image)

		if result.rejected:
			stats["rejected"] += 1

			if not dry_run:
				target = (
					rejected_root
					/ path.parent.name
					/ path.name
				)

				target.parent.mkdir(
					parents=True,
					exist_ok=True,
				)

				shutil.move(
					str(path),
					str(target),
				)

			continue

		same = (
			image.shape == result.cleaned.shape
			and np.array_equal(
				image,
				result.cleaned,
			)
		)

		if same:
			stats["unchanged"] += 1
			continue

		stats["cleaned"] += 1

		if not dry_run:
			cv2.imwrite(
				str(path),
				result.cleaned,
			)

	return stats
