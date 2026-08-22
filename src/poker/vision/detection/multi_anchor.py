from pathlib import Path

import cv2


class MultiAnchorDetector:
	def __init__(self, base_folder, threshold=0.72):
		self.threshold = threshold
		self.groups = {}
		self.group_order = [
			"top_left",
			"top_right",
			"bottom_left",
		]

		base_path = Path(base_folder)

		for group_name in self.group_order:
			group_path = base_path / group_name
			templates = []

			if group_path.exists():
				for image_path in sorted(group_path.glob("*.png")):
					image = cv2.imread(
						str(image_path),
						cv2.IMREAD_GRAYSCALE,
					)

					if image is None:
						continue

					templates.append(
						{
							"name": image_path.name,
							"image": image,
							"width": image.shape[1],
							"height": image.shape[0],
						}
					)

			self.groups[group_name] = templates
			print(
				f"[ANCHOR:{group_name}] Templates loaded: {len(templates)}"
			)

	def find(self, frame):
		gray = cv2.cvtColor(
			frame,
			cv2.COLOR_BGR2GRAY,
		)

		found = {}

		for group_name in self.group_order:
			templates = self.groups[group_name]
			best = None

			for template in templates:
				result = cv2.matchTemplate(
					gray,
					template["image"],
					cv2.TM_CCOEFF_NORMED,
				)

				_, score, _, location = cv2.minMaxLoc(result)

				candidate = {
					"group": group_name,
					"name": template["name"],
					"score": float(score),
					"x": location[0],
					"y": location[1],
					"width": template["width"],
					"height": template["height"],
				}

				if best is None or candidate["score"] > best["score"]:
					best = candidate

			if best is not None and best["score"] >= self.threshold:
				found[group_name] = best

		return found
