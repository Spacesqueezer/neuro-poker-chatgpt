DEFAULT_ROIS = {
	"board": (0.31, 0.38, 0.61, 0.58),
	"pot": (0.39, 0.29, 0.60, 0.37),
	"hero_cards": (0.41, 0.77, 0.59, 0.96),
	"seat_top_left": (0.00, 0.20, 0.20, 0.47),
	"seat_top_center": (0.26, 0.02, 0.50, 0.23),
	"seat_top_right": (0.56, 0.02, 0.79, 0.23),
	"seat_right": (0.81, 0.22, 1.00, 0.50),
	"seat_bottom_right": (0.74, 0.56, 1.00, 0.82),
	"seat_bottom_center": (0.35, 0.67, 0.65, 0.98),
	"seat_bottom_left": (0.00, 0.56, 0.25, 0.82),
	"action_panel": (0.28, 0.85, 0.72, 1.00),
}


def get_rois(config):
	layout = config.get("table_rois")

	if isinstance(layout, dict):
		return layout

	return DEFAULT_ROIS


def scale_roi(frame_width, frame_height, normalized_roi):
	x1, y1, x2, y2 = normalized_roi

	return (
		max(0, int(frame_width * x1)),
		max(0, int(frame_height * y1)),
		min(frame_width, int(frame_width * x2)),
		min(frame_height, int(frame_height * y2)),
	)
