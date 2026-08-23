import cv2


def draw_name_rois(frame, rois, detected_names):
	for seat_name, rect in rois.items():
		x1, y1, x2, y2 = rect

		cv2.rectangle(
			frame,
			(x1, y1),
			(x2, y2),
			(0, 255, 0),
			2,
		)

		label = seat_name

		if seat_name in detected_names and detected_names[seat_name]:
			label = f"{seat_name}: {detected_names[seat_name]}"

		cv2.putText(
			frame,
			label,
			(x1, max(18, y1 - 6)),
			cv2.FONT_HERSHEY_SIMPLEX,
			0.45,
			(0, 255, 0),
			1,
		)

	return frame
