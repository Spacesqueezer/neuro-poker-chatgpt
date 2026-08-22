import cv2


WINDOW_NAME = "Poker Vision Debug"


def show_frame(frame):
	cv2.imshow(WINDOW_NAME, frame)

	key = cv2.waitKey(1) & 0xFF

	if key == ord("q"):
		return False

	return True
