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
	print(
		f"[DEBUG] Preview excluded from capture: "
		f"{exclude_from_capture(WINDOW_NAME)}"
	)

	while True:
		frame = capture.grab()

		anchors = detector.find(frame)

		print("[DEBUG ANCHORS]", anchors)

		if len(anchors) < 3:
			preview = frame.copy()

			cv2.putText(
				preview,
				"WAITING FOR 3 ANCHORS",
				(20, 40),
				cv2.FONT_HERSHEY_SIMPLEX,
				1,
				(0, 0, 255),
				2,
			)

			key = show_frame(
				preview,
				config.get("debug", {}).get("preview_scale", 0.5),
			)

			if key == ord("q"):
				break

			time.sleep(0.1)
			continue

		region = build_preview_region(
			frame,
			anchors,
		)

		if region is None:
			continue

		table_frame = _crop(
			frame,
			region,
		)

		cv2.putText(
			table_frame,
			"TABLE LOCKED",
			(20, 40),
			cv2.FONT_HERSHEY_SIMPLEX,
			1,
			(0, 255, 0),
			2,
		)

		key = show_frame(
			table_frame,
			config.get("debug", {}).get("preview_scale", 0.8),
		)

		if key == ord("q"):
			break

		time.sleep(0.1)

	close()


if __name__ == "__main__":
	run()
