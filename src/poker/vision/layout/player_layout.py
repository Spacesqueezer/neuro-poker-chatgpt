SEAT_LAYOUT = {
	"seat_top_left": {
		"name": (0.08, 0.20, 0.26, 0.28),
		"hole_cards": (0.14, 0.27, 0.30, 0.44),
	},
	"seat_top_center": {
		"name": (0.35, 0.08, 0.53, 0.16),
		"hole_cards": (0.37, 0.16, 0.53, 0.33),
	},
	"seat_top_right": {
		"name": (0.61, 0.08, 0.79, 0.16),
		"hole_cards": (0.58, 0.16, 0.74, 0.33),
	},
	"seat_right": {
		"name": (0.78, 0.30, 0.96, 0.38),
		"hole_cards": (0.70, 0.34, 0.86, 0.51),
	},
	"seat_bottom_right": {
		"name": (0.70, 0.66, 0.88, 0.74),
		"hole_cards": (0.60, 0.58, 0.76, 0.77),
	},
	"seat_bottom_center": {
		"name": (0.41, 0.78, 0.59, 0.86),
		"hole_cards": (0.42, 0.61, 0.58, 0.80),
	},
	"seat_bottom_left": {
		"name": (0.12, 0.66, 0.30, 0.74),
		"hole_cards": (0.24, 0.58, 0.40, 0.77),
	},
}


def scale_roi(frame_width, frame_height, normalized_roi):
	x1, y1, x2, y2 = normalized_roi

	return (
		max(0, int(round(frame_width * x1))),
		max(0, int(round(frame_height * y1))),
		min(frame_width, int(round(frame_width * x2))),
		min(frame_height, int(round(frame_height * y2))),
	)


def build_seat_rois(table_frame):
	height, width = table_frame.shape[:2]
	result = {}

	for seat_name, seat_layout in SEAT_LAYOUT.items():
		result[seat_name] = {
			"name": scale_roi(
				width,
				height,
				seat_layout["name"],
			),
			"hole_cards": scale_roi(
				width,
				height,
				seat_layout["hole_cards"],
			),
		}

	return result
