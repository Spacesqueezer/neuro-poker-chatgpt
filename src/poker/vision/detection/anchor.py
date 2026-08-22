from pathlib import Path

import cv2


class AnchorDetector:
	def __init__(self, folder_path, threshold=0.75):
		self.threshold = threshold
		self.templates = []

		folder = Path(folder_path)

		for image_path in sorted(folder.glob("*.png")):
			image = cv2.imread(
				str(image_path),
				cv2.IMREAD_GRAYSCALE,
			)

			if image is not None:
				self.templates.append(
					{
						"name": image_path.name,
						"image": image,
					}
				)

		print(
			f"[ANCHOR] Templates loaded: {len(self.templates)}"
		)

	def find(self, frame):
		gray = cv2.cvtColor(
			frame,
			cv2.COLOR_BGR2GRAY,
		)

		best = None

		for template in self.templates:
			result = cv2.matchTemplate(
				gray,
				template["image"],
				cv2.TM_CCOEFF_NORMED,
			)

			_, score, _, location = cv2.minMaxLoc(result)

			if best is None or score > best["score"]:
				best = {
					"score": float(score),
					"x": location[0],
					"y": location[1],
					"name": template["name"],
				}

		if best and best["score"] >= self.threshold:
			return best

		return None
