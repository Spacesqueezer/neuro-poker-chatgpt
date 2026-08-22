import time
import cv2

from poker.vision.config import load_vision_config
from poker.vision.capture.screen_capture import ScreenCapture
from poker.vision.debug.viewer import create_window, show_frame, close, WINDOW_NAME
from poker.vision.debug.windows_capture import exclude_from_capture
from poker.vision.project_paths import find_project_root, get_assets_path
from poker.vision.detection.multi_anchor import MultiAnchorDetector
from poker.vision.tracking.table_region import build_preview_region


def _crop(frame, region):
	return frame[
		region.top:region.top + region.height,
		region.left:region.left + region.width,
	]


def _draw_anchor_boxes(frame, anchors):
	colors = {
		"top_left": (0, 255, 0),
		"top_right": (255, 200, 0),
		"bottom_left": (255, 0, 255),
	}

	for group_name, anchor in anchors.items():
		color = colors.get(group_name, (255, 255, 255))

		cv2.rectangle(
			frame,
			(anchor["x"], anchor["y"]),
			(
				anchor["x"] + anchor["width"],
				anchor["y"] + anchor["height"],
			),
			color,
			2,
		)

		cv2.putText(
			frame,
			f"{group_name} {anchor['score']:.3f}",
			(anchor["x"], max(20, anchor["y"] - 8)),
			cv2.FONT_HERSHEY_SIMPLEX,
			0.5,
			color,
			1,
		)


def run():
	config = load_vision_config()

	project_root = find_project_root()
	assets_path = get_assets_path()

	print("[VISION] Started")
	print(f"[PROJECT] {project_root}")
	print(f"[ASSETS] {assets_path}")
	print(f"[CONFIG] Hero: {config['hero_name']}")

	capture = ScreenCapture(
		config["capture"]["monitor"]
	)

	detector = MultiAnchorDetector(
		assets_path / "anchor",
		config["anchor"]["threshold"],
	)

	create_window()
	excluded = exclude_from_capture(WINDOW_NAME)

	print(f"[DEBUG] Preview excluded from capture: {excluded}")

	while True:
		frame = capture.grab()
		anchors = detector.find(frame)

		for group_name in ["top_left", "top_right", "bottom_left"]:
			if group_name in anchors:
				anchor = anchors[group_name]
				print(
					f"[ANCHOR:{group_name}] "
					f"{anchor['name']} score={anchor['score']:.3f} "
					f"x={anchor['x']} y={anchor['y']}"
				)
			else:
				print(f"[ANCHOR:{group_name}] not found")

		preview_frame = frame.copy()
		_draw_anchor_boxes(preview_frame, anchors)

		region = build_preview_region(frame, anchors)

		if region is not None:
			preview_frame = _crop(frame, region)

			cv2.putText(
				preview_frame,
				"THREE ANCHOR PREVIEW",
				(20, 36),
				cv2.FONT_HERSHEY_SIMPLEX,
				0.9,
				(0, 255, 0),
				2,
			)
		else:
			cv2.putText(
				preview_frame,
				"WAITING FOR ALL 3 ANCHORS",
				(20, 36),
				cv2.FONT_HERSHEY_SIMPLEX,
				0.9,
				(0, 0, 255),
				2,
			)

		key = show_frame(
			preview_frame,
			config.get("debug", {}).get("preview_scale", 0.8),
		)

		if key == ord("q"):
			break

		time.sleep(
			1 / config["capture"]["fps_limit"]
		)

	close()


if __name__ == "__main__":
	run()
