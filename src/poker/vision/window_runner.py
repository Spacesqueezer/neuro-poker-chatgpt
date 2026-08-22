import time
import cv2

from poker.vision.window_locator import find_pokerdom_window
from poker.vision.window_capture import WindowCapture


def run():
	capture = WindowCapture()

	while True:
		window = find_pokerdom_window()

		if not window:
			print("[WINDOW] PokerDom not found")
			time.sleep(2)
			continue

		print(
			f"[WINDOW] {window['title']} "
			f"{window['right'] - window['left']}x"
			f"{window['bottom'] - window['top']}"
		)

		frame = capture.grab(window)

		cv2.imshow(
			"PokerDom Window",
			cv2.resize(frame, (900, 700)),
		)

		if cv2.waitKey(1) & 0xFF == ord("q"):
			break

		time.sleep(0.1)

	cv2.destroyAllWindows()


if __name__ == "__main__":
	run()
