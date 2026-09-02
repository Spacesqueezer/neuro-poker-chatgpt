from pathlib import Path

import cv2


DEFAULT_SCALES = (
	0.70,
	0.82,
	0.92,
	1.00,
	1.10,
	1.22,
	1.38,
	1.58,
	1.80,
)


class MultiAnchorDetector:
	def __init__(
		self,
		base_folder,
		threshold=0.72,
	):
		self.threshold = threshold

		self.groups = {}

		self.group_order = [
			"top_left",
			"top_right",
			"bottom_left",
		]

		base_path = Path(
			base_folder
		)

		for group_name in self.group_order:
			group_path = (
				base_path
				/ group_name
			)

			templates = []

			if group_path.exists():
				for image_path in sorted(
					group_path.glob(
						"*.png"
					)
				):
					image = cv2.imread(
						str(
							image_path
						),
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

			self.groups[
				group_name
			] = templates

			print(
				f"[ANCHOR:{group_name}] "
				f"Templates loaded: "
				f"{len(templates)}"
			)

	def find(
		self,
		frame,
		scale_hint=1.0,
		wide_search=False,
	):
		if (
			frame is None
			or frame.size == 0
		):
			return {}

		gray = cv2.cvtColor(
			frame,
			cv2.COLOR_BGR2GRAY,
		)

		if wide_search:
			scales = DEFAULT_SCALES
		else:
			scale_hint = max(
				0.45,
				min(
					2.25,
					float(
						scale_hint
						or 1.0
					),
				),
			)

			scales = (
				scale_hint * 0.88,
				scale_hint,
				scale_hint * 1.12,
			)

		found = {}

		for group_name in self.group_order:
			templates = self.groups[
				group_name
			]

			best = None

			for template in templates:
				candidate = self._match_template(
					gray,
					group_name,
					template,
					scales,
				)

				if candidate is None:
					continue

				if (
					best is None
					or candidate["score"]
					> best["score"]
				):
					best = candidate

			if (
				best is not None
				and best["score"]
				>= self.threshold
			):
				found[
					group_name
				] = best

		return found

	def _match_template(
		self,
		gray,
		group_name,
		template,
		scales,
	):
		best = None

		for scale in scales:
			scale = max(
				0.40,
				min(
					2.40,
					float(scale),
				),
			)

			if abs(
				scale - 1.0
			) < 0.015:
				image = template[
					"image"
				]
			else:
				width = max(
					3,
					int(
						round(
							template[
								"width"
							]
							* scale
						)
					),
				)

				height = max(
					3,
					int(
						round(
							template[
								"height"
							]
							* scale
						)
					),
				)

				image = cv2.resize(
					template["image"],
					(
						width,
						height,
					),
					interpolation=(
						cv2.INTER_AREA
						if scale < 1.0
						else cv2.INTER_CUBIC
					),
				)

			height, width = (
				image.shape[:2]
			)

			if (
				height
				>= gray.shape[0]
				or width
				>= gray.shape[1]
			):
				continue

			result = cv2.matchTemplate(
				gray,
				image,
				cv2.TM_CCOEFF_NORMED,
			)

			_, score, _, location = (
				cv2.minMaxLoc(
					result
				)
			)

			candidate = {
				"group": group_name,
				"name": template[
					"name"
				],
				"score": float(
					score
				),
				"x": location[0],
				"y": location[1],
				"width": width,
				"height": height,
				"scale": scale,
			}

			if (
				best is None
				or candidate["score"]
				> best["score"]
			):
				best = candidate

		return best
