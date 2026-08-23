from dataclasses import dataclass


@dataclass
class TableRegion:
	left: int
	top: int
	width: int
	height: int


def build_preview_region(frame, anchors):
	required = [
		"top_left",
		"top_right",
		"bottom_left",
	]

	if not all(key in anchors for key in required):
		return None

	top_left = anchors["top_left"]
	top_right = anchors["top_right"]
	bottom_left = anchors["bottom_left"]

	left = min(
		top_left["x"],
		bottom_left["x"],
	)

	top = min(
		top_left["y"],
		top_right["y"],
	)

	right = max(
		top_right["x"] + top_right["width"],
		top_left["x"] + top_left["width"],
	)

	bottom = max(
		bottom_left["y"] + bottom_left["height"],
	)

	width = right - left
	height = bottom - top

	if width < 300 or height < 200:
		return None

	return TableRegion(
		left=left,
		top=top,
		width=width,
		height=height,
	)
