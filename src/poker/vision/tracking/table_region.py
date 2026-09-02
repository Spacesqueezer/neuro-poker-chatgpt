from dataclasses import dataclass

import numpy as np


@dataclass
class TableRegion:
	left: int
	top: int
	width: int
	height: int

	@property
	def right(self):
		return (
			self.left
			+ self.width
		)

	@property
	def bottom(self):
		return (
			self.top
			+ self.height
		)


def build_preview_region(
	frame,
	anchors,
):
	required = [
		"top_left",
		"top_right",
		"bottom_left",
	]

	if not all(
		name in anchors
		for name in required
	):
		return None

	top_left = anchors[
		"top_left"
	]

	top_right = anchors[
		"top_right"
	]

	bottom_left = anchors[
		"bottom_left"
	]

	# Размеры margin масштабируются вместе с найденными anchor templates.
	# Раньше тут были жёсткие ±30/50 px, что особенно неприятно
	# проявлялось после изменения размера окна PokerDom.
	scale = estimate_anchor_scale(
		anchors
	)

	left_margin = int(
		round(
			30 * scale
		)
	)

	top_margin = int(
		round(
			30 * scale
		)
	)

	right_margin = int(
		round(
			50 * scale
		)
	)

	bottom_margin = int(
		round(
			50 * scale
		)
	)

	left = (
		top_left["x"]
		- left_margin
	)

	top = (
		top_left["y"]
		- top_margin
	)

	right = (
		top_right["x"]
		+ top_right["width"]
		+ right_margin
	)

	bottom = (
		bottom_left["y"]
		+ bottom_left["height"]
		+ bottom_margin
	)

	frame_height, frame_width = (
		frame.shape[:2]
	)

	left = max(
		0,
		min(
			left,
			frame_width - 1,
		),
	)

	top = max(
		0,
		min(
			top,
			frame_height - 1,
		),
	)

	right = max(
		left + 1,
		min(
			right,
			frame_width,
		),
	)

	bottom = max(
		top + 1,
		min(
			bottom,
			frame_height,
		),
	)

	region = TableRegion(
		left=left,
		top=top,
		width=right - left,
		height=bottom - top,
	)

	if not region_is_sane(
		frame,
		region,
	):
		return None

	return region


def estimate_anchor_scale(
	anchors,
):
	scales = []

	for anchor in anchors.values():
		scale = anchor.get(
			"scale"
		)

		if scale is None:
			continue

		scales.append(
			float(scale)
		)

	if not scales:
		return 1.0

	return float(
		np.median(
			scales
		)
	)


def region_is_sane(
	frame,
	region,
):
	if region is None:
		return False

	frame_height, frame_width = (
		frame.shape[:2]
	)

	if (
		region.width <= 0
		or region.height <= 0
	):
		return False

	width_ratio = (
		region.width
		/ max(
			frame_width,
			1,
		)
	)

	height_ratio = (
		region.height
		/ max(
			frame_height,
			1,
		)
	)

	# PokerDom может быть маленьким окном или почти на весь экран.
	# Ограничения нужны только для отбрасывания явных ложных anchor-lock.
	if (
		width_ratio < 0.18
		or height_ratio < 0.18
	):
		return False

	if (
		width_ratio > 1.01
		or height_ratio > 1.01
	):
		return False

	aspect = (
		region.width
		/ max(
			region.height,
			1,
		)
	)

	return (
		1.15
		<= aspect
		<= 2.45
	)


def region_changed(
	old_region,
	new_region,
):
	if (
		old_region is None
		or new_region is None
	):
		return True

	old_center_x = (
		old_region.left
		+ old_region.width * 0.5
	)

	old_center_y = (
		old_region.top
		+ old_region.height * 0.5
	)

	new_center_x = (
		new_region.left
		+ new_region.width * 0.5
	)

	new_center_y = (
		new_region.top
		+ new_region.height * 0.5
	)

	center_shift = (
		(
			(
				new_center_x
				- old_center_x
			) ** 2
			+ (
				new_center_y
				- old_center_y
			) ** 2
		) ** 0.5
	)

	center_threshold = max(
		14.0,
		min(
			old_region.width,
			old_region.height,
		)
		* 0.025,
	)

	width_change = abs(
		new_region.width
		- old_region.width
	) / max(
		old_region.width,
		1,
	)

	height_change = abs(
		new_region.height
		- old_region.height
	) / max(
		old_region.height,
		1,
	)

	return (
		center_shift
		>= center_threshold
		or width_change
		>= 0.035
		or height_change
		>= 0.035
	)
