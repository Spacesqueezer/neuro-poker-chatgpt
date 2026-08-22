from dataclasses import dataclass


@dataclass
class TableRegion:
	left: int
	top: int
	width: int
	height: int


def _clamp(value, minimum, maximum):
	return max(minimum, min(value, maximum))


def build_preview_region(frame, anchors):
	required = [
		"top_left",
		"top_right",
		"bottom_left",
	]

	if not all(name in anchors for name in required):
		return None

	frame_height, frame_width = frame.shape[:2]

	top_left = anchors["top_left"]
	top_right = anchors["top_right"]
	bottom_left = anchors["bottom_left"]

	left = min(
		top_left["x"],
		bottom_left["x"],
	) - 12

	top = min(
		top_left["y"],
		top_right["y"],
	) - 42

	right = max(
		top_right["x"] + top_right["width"],
		top_left["x"] + top_left["width"],
	) + 44

	bottom = max(
		bottom_left["y"] + bottom_left["height"],
		top_left["y"] + top_left["height"],
	) + 18

	left = _clamp(left, 0, frame_width - 1)
	top = _clamp(top, 0, frame_height - 1)
	right = _clamp(right, left + 1, frame_width)
	bottom = _clamp(bottom, top + 1, frame_height)

	return TableRegion(
		left=left,
		top=top,
		width=right - left,
		height=bottom - top,
	)
