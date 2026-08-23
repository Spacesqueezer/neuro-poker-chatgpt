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

	if not all(name in anchors for name in required):
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

	right = top_right["x"] + top_right["width"]

	bottom = bottom_left["y"] + bottom_left["height"]

	padding_x = 40
	padding_y = 40

	left = max(0, left - padding_x)
	top = max(0, top - padding_y)

	right += padding_x
	bottom += padding_y

	return TableRegion(
		left=left,
		top=top,
		width=right - left,
		height=bottom - top,
	)