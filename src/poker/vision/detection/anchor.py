from pathlib import Path

import cv2


class AnchorDetector:
	def __init__(self, template_path, threshold=0.75):
		self.threshold = threshold
		template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)

		if template is None:
			raise FileNotFoundError(template_path)

		self.template = template

	def find(self, frame):
		gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

		result = cv2.matchTemplate(
			gray,
			self.template,
			cv2.TM_CCOEFF_NORMED,
		)

		_, score, _, location = cv2.minMaxLoc(result)

		if score < self.threshold:
			return None

		return {
			"score": float(score),
			"left": location[0],
			"top": location[1],
			"width": self.template.shape[1],
			"height": self.template.shape[0],
		}
