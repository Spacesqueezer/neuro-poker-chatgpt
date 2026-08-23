from pathlib import Path
from datetime import datetime
import cv2


class CaptureManager:
	def __init__(self, folder="captures"):
		self.folder = Path(folder)
		self.folder.mkdir(parents=True, exist_ok=True)

	def save(self, frame):
		filename = self.folder / (
			f"table_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
		)

		cv2.imwrite(str(filename), frame)
		print(f"[CAPTURE] Saved: {filename}")

		return filename
