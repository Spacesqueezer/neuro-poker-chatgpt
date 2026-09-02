import cv2
import numpy as np


# PokerDom повторяет rank крупно справа. Для распознавания он вообще не нужен.
# Работаем только с маленькими glyph в левом верхнем углу карты.
CORNER_LEFT = 0.07
CORNER_RIGHT = 0.43

RANK_TOP = 0.05
RANK_BOTTOM = 0.43

SUIT_TOP = 0.40
SUIT_BOTTOM = 0.73


def rank_feature(card_frame):
	return _corner_glyph_feature(
		card_frame,
		top=RANK_TOP,
		bottom=RANK_BOTTOM,
		left=CORNER_LEFT,
		right=CORNER_RIGHT,
		output_size=(56, 56),
		min_area_ratio=0.010,
		combine_rank_parts=True,
		min_height_ratio=0.28,
		min_aspect=0.06,
		max_aspect=3.0,
	)


def suit_feature(card_frame):
	return _corner_glyph_feature(
		card_frame,
		top=SUIT_TOP,
		bottom=SUIT_BOTTOM,
		left=CORNER_LEFT,
		right=CORNER_RIGHT,
		output_size=(40, 40),
		min_area_ratio=0.012,
		combine_rank_parts=False,
		min_height_ratio=0.18,
		min_aspect=0.12,
		max_aspect=2.2,
	)


def _corner_glyph_feature(
	card_frame,
	top,
	bottom,
	left,
	right,
	output_size,
	min_area_ratio,
	combine_rank_parts,
	min_height_ratio,
	min_aspect,
	max_aspect,
):
	if card_frame is None or card_frame.size == 0:
		return None

	height, width = card_frame.shape[:2]

	x1 = int(width * left)
	x2 = int(width * right)
	y1 = int(height * top)
	y2 = int(height * bottom)

	roi = card_frame[
		y1:y2,
		x1:x2,
	]

	if roi.size == 0:
		return None

	mask = _ink_mask(roi)

	candidates = _extract_candidates(
		mask,
		min_area_ratio=min_area_ratio,
		min_height_ratio=min_height_ratio,
		min_aspect=min_aspect,
		max_aspect=max_aspect,
	)

	if not candidates:
		return None

	if combine_rank_parts:
		shape = _combine_rank_candidates(
			mask,
			candidates,
		)
	else:
		shape = _crop_candidate(
			mask,
			max(
				candidates,
				key=lambda item: item["area"],
			),
		)

	if shape is None:
		return None

	return _normalize_glyph(
		shape,
		output_size=output_size,
	)


def _ink_mask(roi):
	hsv = cv2.cvtColor(
		roi,
		cv2.COLOR_BGR2HSV,
	)

	gray = cv2.cvtColor(
		roi,
		cv2.COLOR_BGR2GRAY,
	)

	# Чёрные rank/suit.
	dark = cv2.inRange(
		gray,
		0,
		165,
	)

	# Красные rank/suit. Берём вообще насыщенный цвет, чтобы не зависеть
	# от конкретного оттенка PokerDom/темы.
	colored = cv2.inRange(
		hsv,
		np.array([0, 60, 45], dtype=np.uint8),
		np.array([179, 255, 255], dtype=np.uint8),
	)

	mask = cv2.bitwise_or(dark, colored)

	mask = cv2.morphologyEx(
		mask,
		cv2.MORPH_OPEN,
		cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)),
		iterations=1,
	)

	return mask


def _extract_candidates(
	mask,
	min_area_ratio,
	min_height_ratio,
	min_aspect,
	max_aspect,
):
	contours, _ = cv2.findContours(
		mask,
		cv2.RETR_EXTERNAL,
		cv2.CHAIN_APPROX_SIMPLE,
	)

	if not contours:
		return []

	mask_height, mask_width = mask.shape[:2]
	total_area = float(mask_height * mask_width)

	candidates = []

	for contour in contours:
		area = cv2.contourArea(contour)
		if area <= 0:
			continue

		if area / max(total_area, 1.0) < min_area_ratio:
			continue

		x, y, width, height = cv2.boundingRect(contour)

		if width < 2 or height < 3:
			continue

		if height / max(mask_height, 1) < min_height_ratio:
			continue

		aspect = width / max(height, 1)
		if aspect < min_aspect or aspect > max_aspect:
			continue

		candidates.append({
			"area": area,
			"x": x,
			"y": y,
			"width": width,
			"height": height,
			"aspect": aspect,
		})

	return candidates


def _combine_rank_candidates(mask, candidates):
	if not candidates:
		return None

	largest = max(
		candidates,
		key=lambda item: item["area"],
	)

	mask_width = mask.shape[1]
	max_gap = max(2, int(round(mask_width * 0.22)))
	min_secondary_area = max(largest["area"] * 0.18, 1.0)

	selected = []

	for item in sorted(candidates, key=lambda part: part["x"]):
		if item["area"] < min_secondary_area and item is not largest:
			continue

		if _vertical_overlap_ratio(item, largest) < 0.35:
			continue

		gap = _horizontal_gap(item, largest)
		if gap > max_gap:
			continue

		selected.append(item)

	if not selected:
		selected = [largest]

	x1 = min(item["x"] for item in selected)
	y1 = min(item["y"] for item in selected)
	x2 = max(item["x"] + item["width"] for item in selected)
	y2 = max(item["y"] + item["height"] for item in selected)

	return mask[y1:y2, x1:x2]


def _vertical_overlap_ratio(left, right):
	start = max(left["y"], right["y"])
	end = min(left["y"] + left["height"], right["y"] + right["height"])
	overlap = max(0, end - start)
	base = min(left["height"], right["height"])
	if base <= 0:
		return 0.0
	return overlap / float(base)


# Если contour пересекается по X, gap = 0.
def _horizontal_gap(left, right):
	left_end = left["x"] + left["width"]
	right_end = right["x"] + right["width"]
	if left_end < right["x"]:
		return right["x"] - left_end
	if right_end < left["x"]:
		return left["x"] - right_end
	return 0


def _crop_candidate(mask, candidate):
	x = candidate["x"]
	y = candidate["y"]
	width = candidate["width"]
	height = candidate["height"]
	return mask[y:y + height, x:x + width]


def _normalize_glyph(shape, output_size):
	target_width, target_height = output_size

	if shape is None or shape.size == 0:
		return None

	height, width = shape.shape[:2]

	if width <= 0 or height <= 0:
		return None

	padding_x = max(2, int(round(target_width * 0.10)))
	padding_y = max(2, int(round(target_height * 0.10)))

	usable_width = max(1, target_width - padding_x * 2)
	usable_height = max(1, target_height - padding_y * 2)

	scale = min(usable_width / width, usable_height / height)

	new_width = max(1, int(round(width * scale)))
	new_height = max(1, int(round(height * scale)))

	resized = cv2.resize(
		shape,
		(new_width, new_height),
		interpolation=cv2.INTER_AREA,
	)

	canvas = np.zeros((target_height, target_width), dtype=np.uint8)

	offset_x = (target_width - new_width) // 2
	offset_y = (target_height - new_height) // 2

	canvas[
		offset_y:offset_y + new_height,
		offset_x:offset_x + new_width,
	] = resized

	return canvas


def similarity(left, right):
	if left is None or right is None:
		return 0.0

	if left.shape != right.shape:
		right = cv2.resize(
			right,
			(left.shape[1], left.shape[0]),
			interpolation=cv2.INTER_AREA,
		)

	left_binary = (left > 127).astype(np.uint8)
	right_binary = (right > 127).astype(np.uint8)

	intersection = np.count_nonzero(left_binary & right_binary)
	union = np.count_nonzero(left_binary | right_binary)

	if union == 0:
		return 0.0

	iou = intersection / float(union)

	diff = cv2.absdiff(left, right)
	pixel_score = max(0.0, 1.0 - float(np.mean(diff)) / 255.0)

	return iou * 0.78 + pixel_score * 0.22
