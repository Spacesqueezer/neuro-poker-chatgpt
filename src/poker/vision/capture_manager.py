from pathlib import Path

import cv2


class CaptureManager:
	def __init__(self, folder="captures"):
		self.folder = Path(folder)
		self.folder.mkdir(parents=True, exist_ok=True)
		self.counter = self._get_counter()

	def _get_counter(self):
		files = list(self.folder.glob("table_*.png"))
		return len(files) + 1

	def save_table_and_names(self, table_frame, name_crops):
		table_path = self.folder / f"table_{self.counter:04d}.png"
		cv2.imwrite(str(table_path), table_frame)

		names_folder = self.folder / f"table_{self.counter:04d}_names"
		names_folder.mkdir(parents=True, exist_ok=True)

		for seat_name, crop in name_crops.items():
			seat_path = names_folder / f"{seat_name}.png"
			cv2.imwrite(str(seat_path), crop)

		print(f"[CAPTURE] Saved {table_path}")
		print(f"[CAPTURE] Saved {names_folder}")
		self.counter += 1
