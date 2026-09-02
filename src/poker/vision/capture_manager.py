from datetime import datetime
from pathlib import Path
import json
import re

import cv2

from poker.vision.detection.cards import crop_card
from poker.vision.detection.player_panels import crop_panel


def _slugify(value):
	if not value:
		return ""

	value = value.strip().lower()
	value = re.sub(r"[^a-z0-9_-]+", "_", value)
	value = value.strip("_")

	return value


def _crop_training_name(panel_frame):
	"""
	Более широкий crop для датасета никнеймов.

	Runtime OCR использует свой узкий ROI, но для обучения нельзя
	отрезать крайние буквы. Левую границу оставляем достаточно широкой,
	при этом не берём самую крайнюю область со статусной иконкой.
	"""
	if panel_frame is None or panel_frame.size == 0:
		return panel_frame

	height, width = panel_frame.shape[:2]

	return panel_frame[
		int(height * 0.01):int(height * 0.56),
		int(width * 0.055):int(width * 0.985),
	]


class CaptureManager:
	def __init__(self, folder="captures"):
		self.folder = Path(folder)
		self.folder.mkdir(
			parents=True,
			exist_ok=True,
		)

	def save_dynamic(
		self,
		table_frame,
		players,
		board_cards=None,
		hero_cards=None,
	):
		timestamp = datetime.now().strftime(
			"%Y%m%d_%H%M%S_%f"
		)

		output = self.folder / f"table_{timestamp}"
		output.mkdir(
			parents=True,
			exist_ok=True,
		)

		cv2.imwrite(
			str(output / "table.png"),
			table_frame,
		)

		player_folder = output / "players"
		player_folder.mkdir(
			parents=True,
			exist_ok=True,
		)

		name_folder = output / "names"
		name_folder.mkdir(
			parents=True,
			exist_ok=True,
		)

		metadata = []

		for player in players:
			panel_frame = crop_panel(
				table_frame,
				player.panel,
			)

			cv2.imwrite(
				str(
					player_folder
					/ f"player_{player.index:02d}.png"
				),
				panel_frame,
			)

			name_frame = _crop_training_name(
				panel_frame
			)

			safe_name = _slugify(
				getattr(
					player,
					"name",
					"",
				)
			)

			filename = (
				f"name_{player.index:02d}"
			)

			if safe_name:
				filename += (
					f"_{safe_name}"
				)

			cv2.imwrite(
				str(
					name_folder
					/ f"{filename}.png"
				),
				name_frame,
			)

			metadata.append(
				{
					"index": player.index,
					"name": getattr(
						player,
						"name",
						"",
					),
					"is_hero": getattr(
						player,
						"is_hero",
						False,
					),
					"action": getattr(
						player,
						"action",
						None,
					),
				}
			)

		card_folder = output / "cards"
		card_folder.mkdir(
			parents=True,
			exist_ok=True,
		)

		for prefix, cards in (
			("board", board_cards or []),
			("hero", hero_cards or []),
		):
			for index, card in enumerate(cards):
				card_frame = crop_card(
					table_frame,
					card,
				)

				cv2.imwrite(
					str(
						card_folder
						/ f"{prefix}_{index:02d}.png"
					),
					card_frame,
				)

		with open(
			output / "players.json",
			"w",
			encoding="utf-8",
		) as file:
			json.dump(
				metadata,
				file,
				ensure_ascii=False,
				indent=2,
			)

		print(
			f"[CAPTURE] Saved: {output} "
			f"({len(players)} players, "
			f"{len(board_cards or [])} board cards, "
			f"{len(hero_cards or [])} hero cards, "
			f"{len(players)} name crops)"
		)

		return output
