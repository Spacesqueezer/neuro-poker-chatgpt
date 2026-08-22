import time
from pathlib import Path

import cv2

from poker.vision.config import load_vision_config
from poker.vision.capture.screen_capture import ScreenCapture
from poker.vision.detection.anchor import AnchorDetector
from poker.vision.project_paths import get_assets_path, find_project_root
from poker.vision.debug.viewer import show_frame


def run():
	config = load_vision_config()

	root = find_project_root()
	assets = get_assets_path()

	print("[VISION] Started")
	print(f"[PROJECT] {root}")
	print(f"[ASSETS] {assets}")
	print(f"[CONFIG] Hero: {config['hero_name']}")

	anchor_folder = assets / "anchor"

	print(f"[ANCHOR] Folder: {anchor_folder}")

	anchor = AnchorDetector(
		anchor_folder,
		config["anchor"]["threshold"],
	)

	capture = ScreenCapture(
		config["capture"]["monitor"]
	)

	running = True

	while running:
		frame = capture.grab()

		found = anchor.find(frame)

		if found:
			print(
				f"[ANCHOR] Found {found['name']} "
				f"score={found['score']:.3f}"
			)

			cv2.rectangle(
				frame,
				(
					found["x"],
					found["y"],
				),
				(
					found["x"] + 100,
					found["y"] + 50,
				),
				(0, 255, 0),
				2,
			)
		else:
			print("[SEARCH] Anchor not found")

		running = show_frame(frame)

		time.sleep(
			1 / config["capture"]["fps_limit"]
		)

	cv2.destroyAllWindows()


if __name__ == "__main__":
	run()
