DEFAULT_NAME_ROIS = {
	"seat_top_left": (0.02, 0.39, 0.17, 0.47),
	"seat_top_center": (0.59, 0.22, 0.75, 0.30),
	"seat_right": (0.84, 0.39, 0.98, 0.47),
	"seat_bottom_right": (0.81, 0.72, 0.97, 0.80),
	"seat_bottom_center": (0.43, 0.84, 0.59, 0.92),
	"seat_bottom_left": (0.05, 0.72, 0.21, 0.80),
}


def get_name_rois(config):
	layout = config.get("player_name_rois")

	if isinstance(layout, dict):
		return layout

	return DEFAULT_NAME_ROIS


def scale_roi(frame_width, frame_height, normalized_roi):
	x1, y1, x2, y2 = normalized_roi

	return (
		int(frame_width * x1),
		int(frame_height * y1),
		int(frame_width * x2),
		int(frame_height * y2),
	)
