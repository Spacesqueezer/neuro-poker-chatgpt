import time

import cv2

from poker.vision.config import load_vision_config
from poker.vision.capture.screen_capture import ScreenCapture
from poker.vision.debug.viewer import create_window, show_frame, close, WINDOW_NAME
from poker.vision.debug.windows_capture import exclude_from_capture
from poker.vision.project_paths import find_project_root, get_assets_path
from poker.vision.detection.multi_anchor import MultiAnchorDetector
from poker.vision.tracking.table_region import build_preview_region
from poker.vision.layout.player_layout import get_name_rois, scale_roi
from poker.vision.ocr.name_reader import read_player_name
from poker.vision.roi_debug import draw_name_rois
from poker.vision.capture_manager import CaptureManager


def _crop(frame, region):
	return frame[
		region.top:region.top + region.height,
		region.left:region.left + region.width,
	]


def _extract_name_rois(table_frame, config):
	height, width = table_frame.shape[:2]
	normalized_rois = get_name_rois(config)

	scaled_rois = {}

	for seat_name, normalized_roi in normalized_rois.items():
		scaled_rois[seat_name] = scale_roi(
			width,
			height,
			normalized_roi,
		)

	return scaled_rois


def _extract_name_crops(table_frame, scaled_rois):
	crops = {}

	for seat_name, rect in scaled_rois.items():
		x1, y1, x2, y2 = rect
		crops[seat_name] = table_frame[y1:y2, x1:x2].copy()

	return crops


def _detect_names(name_crops):
	detected = {}

	for seat_name, crop in name_crops.items():
		detected[seat_name] = read_player_name(crop)

	return detected


def _print_names(detected_names):
	ordered = [
		"seat_top_left",
		"seat_top_center",
		"seat_right",
		"seat_bottom_right",
		"seat_bottom_center",
		"seat_bottom_left",
	]

	parts = []

	for seat_name in ordered:
		name = detected_names.get(seat_name, "")

		if not name:
			name = "?"

		parts.append(f"{seat_name}={name}")

	print("[PLAYERS] " + " | ".join(parts))


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

	capture_manager = CaptureManager(
		config.get("captures_folder", "captures")
	)

	create_window()
	excluded = exclude_from_capture(WINDOW_NAME)

	print(f"[DEBUG] Preview excluded from capture: {excluded}")

	last_print_time = 0.0

	while True:
		frame = capture.grab()
		anchors = detector.find(frame)
		region = build_preview_region(frame, anchors)

		if region is None:
			preview_frame = frame.copy()

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

			time.sleep(1 / config["capture"]["fps_limit"])
			continue

		table_frame = _crop(frame, region)
		scaled_rois = _extract_name_rois(table_frame, config)
		name_crops = _extract_name_crops(table_frame, scaled_rois)
		detected_names = _detect_names(name_crops)

		debug_frame = table_frame.copy()
		draw_name_rois(debug_frame, scaled_rois, detected_names)

		cv2.putText(
			debug_frame,
			"PLAYER NAME DETECTION",
			(20, 36),
			cv2.FONT_HERSHEY_SIMPLEX,
			0.9,
			(0, 255, 0),
			2,
		)

		now = time.time()

		if now - last_print_time >= 1.0:
			_print_names(detected_names)
			last_print_time = now

		key = show_frame(
			debug_frame,
			config.get("debug", {}).get("preview_scale", 0.8),
		)

		if key == ord("q"):
			break

		if key == 0x71:
			capture_manager.save_table_and_names(
				table_frame,
				name_crops,
			)

		time.sleep(1 / config["capture"]["fps_limit"])

	close()


if __name__ == "__main__":
	run()
