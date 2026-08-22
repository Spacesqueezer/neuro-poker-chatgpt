import time
from pathlib import Path

import cv2

from poker.vision.config import load_vision_config
from poker.vision.capture.screen_capture import ScreenCapture
from poker.vision.detection.anchor import AnchorDetector


BASE_DIR = Path(__file__).resolve().parents[4]


def run():
	config = load_vision_config()

	print("[VISION] Started")
	print(f"[CONFIG] Hero: {config['hero_name']}")

	capture = ScreenCapture(
		config["capture"]["monitor"]
	)

	anchor = AnchorDetector(
		BASE_DIR / "assets" / "pokerdom_anchor.png",
		config["anchor"]["threshold"],
	)

	while True:
		frame = capture.grab()

		found = anchor.find(frame)

		if found:
			print(
				f"[ANCHOR] Found score={found['score']:.3f} "
				f"x={found['left']} y={found['top']}"
			)
		else:
			print("[SEARCH] Anchor not found")

		time.sleep(1 / config["capture"]["fps_limit"])


if __name__ == "__main__":
	run()
