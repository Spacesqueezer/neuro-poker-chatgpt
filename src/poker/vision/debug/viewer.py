import cv2


WINDOW_NAME = "Poker Vision Debug"


def create_window():
	cv2.namedWindow(
		WINDOW_NAME,
		cv2.WINDOW_NORMAL,
	)

	cv2.resizeWindow(
		WINDOW_NAME,
		1100,
		700,
	)


def crop_region(frame, region):
	return frame[
		region.top:region.top + region.height,
		region.left:region.left + region.width,
	]


def show_frame(frame, scale=0.8):
	height, width = frame.shape[:2]

	resized = cv2.resize(
		frame,
		(
			int(width * scale),
			int(height * scale),
		),
		interpolation=cv2.INTER_AREA,
	)

	cv2.imshow(
		WINDOW_NAME,
		resized,
	)

	return cv2.waitKey(1) & 0xFF


def close():
	cv2.destroyAllWindows()
