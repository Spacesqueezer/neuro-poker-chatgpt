from pathlib import Path
from datetime import datetime
import cv2


class UnknownCollector:
	def __init__(self, folder="assets/unknown"):
		self.folder = Path(folder)
		self.folder.mkdir(parents=True, exist_ok=True)

	def save(self, image, category="regions"):
		target = self.folder / category
		target.mkdir(parents=True, exist_ok=True)

		filename = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".png"

		cv2.imwrite(
			str(target / filename),
			image,
		)

		return target / filename
