from datetime import datetime
from pathlib import Path
import json
import re

import cv2

from poker.vision.detection.cards import crop_card
from poker.vision.detection.player_panels import (
	crop_name_from_panel,
	crop_panel,
)
from poker.vision.recognition.card_recognizer import CardRecognizer


RED_CARD = (45, 45, 235)
BLACK_CARD = (20, 20, 20)
BOARD_ROI = (0, 220, 255)
HERO_ROI = (0, 255, 0)
PLAYER_ROI = (255, 0, 255)
HERO_PLAYER_ROI = (0, 255, 0)


def _slugify(value):
	if not value:
		return ""

	value = value.strip().lower()
	value = re.sub(
		r"[^a-z0-9_]+",
		"_",
		value,
	)
	value = value.strip("_")

	return value


def _rect_dict(rect):
	x1, y1, x2, y2 = rect

	return {
		"x": int(x1),
		"y": int(y1),
		"width": int(x2 - x1),
		"height": int(y2 - y1),
		"x2": int(x2),
		"y2": int(y2),
		"center_x": int(
			round(
				(x1 + x2) / 2
			)
		),
		"center_y": int(
			round(
				(y1 + y2) / 2
			)
		),
	}


def _card_parts(value):
	value = str(
		value or ""
	).strip()

	if len(value) != 2:
		return (
			value or "?",
			"",
		)

	return (
		value[0].upper(),
		value[1].lower(),
	)


def _draw_suit(
	frame,
	x,
	y,
	suit,
	scale=1.0,
):
	color = (
		RED_CARD
		if suit in {
			"h",
			"d",
		}
		else BLACK_CARD
	)

	size = max(
		5,
		int(
			round(
				7 * scale
			)
		),
	)

	if suit == "h":
		radius = max(
			2,
			size // 3,
		)

		cv2.circle(
			frame,
			(
				x - radius,
				y - radius,
			),
			radius,
			color,
			-1,
		)

		cv2.circle(
			frame,
			(
				x + radius,
				y - radius,
			),
			radius,
			color,
			-1,
		)

		points = [
			(
				x - radius * 2,
				y - radius,
			),
			(
				x + radius * 2,
				y - radius,
			),
			(
				x,
				y + radius * 3,
			),
		]

		cv2.fillConvexPoly(
			frame,
			__import__(
				"numpy"
			).array(
				points,
				dtype="int32",
			),
			color,
		)

	elif suit == "d":
		points = [
			(
				x,
				y - size,
			),
			(
				x + size,
				y,
			),
			(
				x,
				y + size,
			),
			(
				x - size,
				y,
			),
		]

		cv2.fillConvexPoly(
			frame,
			__import__(
				"numpy"
			).array(
				points,
				dtype="int32",
			),
			color,
		)

	elif suit == "c":
		radius = max(
			2,
			size // 3,
		)

		for dx, dy in (
			(
				0,
				-radius,
			),
			(
				-radius,
				radius // 2,
			),
			(
				radius,
				radius // 2,
			),
		):
			cv2.circle(
				frame,
				(
					x + dx,
					y + dy,
				),
				radius,
				color,
				-1,
			)

		cv2.rectangle(
			frame,
			(
				x - max(
					1,
					radius // 2,
				),
				y + radius // 2,
			),
			(
				x + max(
					1,
					radius // 2,
				),
				y + radius * 2,
			),
			color,
			-1,
		)

	elif suit == "s":
		radius = max(
			2,
			size // 3,
		)

		points = [
			(
				x,
				y - radius * 3,
			),
			(
				x - radius * 2,
				y,
			),
			(
				x + radius * 2,
				y,
			),
		]

		cv2.fillConvexPoly(
			frame,
			__import__(
				"numpy"
			).array(
				points,
				dtype="int32",
			),
			color,
		)

		cv2.circle(
			frame,
			(
				x - radius,
				y,
			),
			radius,
			color,
			-1,
		)

		cv2.circle(
			frame,
			(
				x + radius,
				y,
			),
			radius,
			color,
			-1,
		)

		cv2.rectangle(
			frame,
			(
				x - max(
					1,
					radius // 2,
				),
				y,
			),
			(
				x + max(
					1,
					radius // 2,
				),
				y + radius * 2,
			),
			color,
			-1,
		)


def _draw_card_label(
	frame,
	card,
	value,
	prefix,
	roi_color,
):
	x1, y1, x2, y2 = card.rect

	cv2.rectangle(
		frame,
		(
			x1,
			y1,
		),
		(
			x2,
			y2,
		),
		roi_color,
		2,
	)

	rank, suit = _card_parts(
		value
	)

	label_y = max(
		25,
		y1 - 6,
	)

	label_width = 80

	cv2.rectangle(
		frame,
		(
			x1,
			label_y - 22,
		),
		(
			x1 + label_width,
			label_y + 4,
		),
		(245, 245, 245),
		-1,
	)

	cv2.putText(
		frame,
		f"{prefix}:{rank}",
		(
			x1 + 4,
			label_y - 3,
		),
		cv2.FONT_HERSHEY_SIMPLEX,
		0.50,
		(
			RED_CARD
			if suit in {
				"h",
				"d",
			}
			else BLACK_CARD
		),
		1,
		cv2.LINE_AA,
	)

	if suit:
		_draw_suit(
			frame,
			x1 + 66,
			label_y - 8,
			suit,
			scale=0.75,
		)


class CaptureManager:
	def __init__(
		self,
		folder="captures",
	):
		self.folder = Path(
			folder
		)

		self.folder.mkdir(
			parents=True,
			exist_ok=True,
		)

		# Recognition при capture запускается отдельно.
		# S нажимается вручную, поэтому здесь важнее диагностическая
		# полнота, чем несколько дополнительных миллисекунд.
		self.card_recognizer = (
			CardRecognizer()
		)

	def save_dynamic(
		self,
		table_frame,
		players,
		board_cards=None,
		hero_cards=None,
	):
		board_cards = list(
			board_cards or []
		)

		hero_cards = list(
			hero_cards or []
		)

		timestamp = (
			datetime.now().strftime(
				"%Y%m%d_%H%M%S_%f"
			)
		)

		output = (
			self.folder
			/ f"table_{timestamp}"
		)

		output.mkdir(
			parents=True,
			exist_ok=True,
		)

		cv2.imwrite(
			str(
				output
				/ "table.png"
			),
			table_frame,
		)

		annotated = (
			table_frame.copy()
		)

		board_values = []
		hero_values = []

		try:
			if board_cards:
				board_values = (
					self.card_recognizer
					.recognize_many(
						table_frame,
						board_cards,
					)
				)
		except Exception as error:
			board_values = [
				f"?error:{error}"
			]

		try:
			if hero_cards:
				hero_values = (
					self.card_recognizer
					.recognize_many(
						table_frame,
						hero_cards,
					)
				)
		except Exception as error:
			hero_values = [
				f"?error:{error}"
			]

		player_folder = (
			output / "players"
		)

		player_folder.mkdir(
			parents=True,
			exist_ok=True,
		)

		name_folder = (
			output / "names"
		)

		name_folder.mkdir(
			parents=True,
			exist_ok=True,
		)

		action_folder = (
			output / "actions"
		)

		action_folder.mkdir(
			parents=True,
			exist_ok=True,
		)

		player_metadata = []

		for player in players:
			panel = player.panel

			panel_frame = (
				crop_panel(
					table_frame,
					panel,
				)
			)

			cv2.imwrite(
				str(
					player_folder
					/ (
						f"player_"
						f"{player.index:02d}.png"
					)
				),
				panel_frame,
			)

			# IMPORTANT: capture exactly the same nickname ROI that
			# runtime OCR sees. The labeler and monitor must no longer
			# debug two different crops.
			name_frame = (
				crop_name_from_panel(
					panel_frame
				)
			)

			name = getattr(
				player,
				"name",
				"",
			)

			safe_name = (
				_slugify(
					name
				)
			)

			filename = (
				f"name_"
				f"{player.index:02d}"
			)

			if safe_name:
				filename += (
					f"_{safe_name}"
				)

			action = getattr(
				player,
				"action",
				None,
			)

			# Action overlay не является nickname sample.
			# Не кладём его в names/, иначе база обучения постепенно
			# загрязняется зелёными/оранжевыми надписями действий.
			if action:
				cv2.imwrite(
					str(
						action_folder
						/ (
							f"action_"
							f"{player.index:02d}.png"
						)
					),
					name_frame,
				)
			else:
				cv2.imwrite(
					str(
						name_folder
						/ f"{filename}.png"
					),
					name_frame,
				)

			is_hero = bool(
				getattr(
					player,
					"is_hero",
					False,
				)
			)

			x1, y1, x2, y2 = (
				panel.rect
			)

			color = (
				HERO_PLAYER_ROI
				if is_hero
				else PLAYER_ROI
			)

			cv2.rectangle(
				annotated,
				(
					x1,
					y1,
				),
				(
					x2,
					y2,
				),
				color,
				2,
			)

			label = (
				f"{player.index}:"
				f"{name or '?'}"
			)

			if is_hero:
				label = (
					"HERO "
					+ label
				)

			if action:
				label += (
					f" [{action}]"
				)

			cv2.putText(
				annotated,
				label,
				(
					x1,
					max(
						18,
						y1 - 5,
					),
				),
				cv2.FONT_HERSHEY_SIMPLEX,
				0.45,
				color,
				1,
				cv2.LINE_AA,
			)

			player_metadata.append(
				{
					"index": int(
						player.index
					),
					"name": name,
					"raw_name": getattr(
						player,
						"raw_name",
						"",
					),
					"confidence": float(
						getattr(
							player,
							"confidence",
							0.0,
						)
					),
					"identity_pending": bool(
						getattr(
							player,
							"identity_pending",
							False,
						)
					),
					"is_hero": (
						is_hero
					),
					"action": action,
					"panel_roi": (
						_rect_dict(
							panel.rect
						)
					),
				}
			)

		card_folder = (
			output / "cards"
		)

		card_folder.mkdir(
			parents=True,
			exist_ok=True,
		)

		card_metadata = {
			"board": [],
			"hero": [],
		}

		for (
			prefix,
			cards,
			values,
			color,
		) in (
			(
				"board",
				board_cards,
				board_values,
				BOARD_ROI,
			),
			(
				"hero",
				hero_cards,
				hero_values,
				HERO_ROI,
			),
		):
			for index, card in enumerate(
				cards
			):
				value = (
					values[index]
					if index
					< len(values)
					else "?"
				)

				card_frame = (
					crop_card(
						table_frame,
						card,
					)
				)

				safe_value = (
					re.sub(
						r"[^A-Za-z0-9?]+",
						"",
						str(value),
					)
					or "unknown"
				)

				cv2.imwrite(
					str(
						card_folder
						/ (
							f"{prefix}_"
							f"{index:02d}_"
							f"{safe_value}.png"
						)
					),
					card_frame,
				)

				_draw_card_label(
					annotated,
					card,
					value,
					(
						"B"
						if prefix
						== "board"
						else "H"
					),
					color,
				)

				card_metadata[
					prefix
				].append(
					{
						"index": index,
						"value": value,
						"roi": (
							_rect_dict(
								card.rect
							)
						),
					}
				)

		cv2.imwrite(
			str(
				output
				/ "table_annotated.png"
			),
			annotated,
		)

		metadata = {
			"timestamp": timestamp,
			"table": {
				"width": int(
					table_frame.shape[1]
				),
				"height": int(
					table_frame.shape[0]
				),
			},
			"players": player_metadata,
			"cards": card_metadata,
			"summary": {
				"player_count": len(
					player_metadata
				),
				"board_box_count": len(
					board_cards
				),
				"hero_box_count": len(
					hero_cards
				),
				"board_values": (
					board_values
				),
				"hero_values": (
					hero_values
				),
			},
		}

		with open(
			output / "capture.json",
			"w",
			encoding="utf-8",
		) as file:
			json.dump(
				metadata,
				file,
				ensure_ascii=False,
				indent=2,
			)

		# Старое имя сохраняем для совместимости со старым tooling.
		with open(
			output / "players.json",
			"w",
			encoding="utf-8",
		) as file:
			json.dump(
				player_metadata,
				file,
				ensure_ascii=False,
				indent=2,
			)

		log_lines = [
			(
				f"CAPTURE {timestamp}"
			),
			(
				"TABLE "
				f"{table_frame.shape[1]}x"
				f"{table_frame.shape[0]}"
			),
			(
				"BOARD "
				f"boxes={len(board_cards)} "
				f"cards={board_values}"
			),
			(
				"HERO "
				f"boxes={len(hero_cards)} "
				f"cards={hero_values}"
			),
			"",
			"PLAYERS",
		]

		for player in player_metadata:
			roi = player[
				"panel_roi"
			]

			log_lines.append(
				(
					f"#{player['index']} "
					f"name={player['name']!r} "
					f"raw={player['raw_name']!r} "
					f"pending={player['identity_pending']} "
					f"conf={player['confidence']:.2f} "
					f"hero={player['is_hero']} "
					f"action={player['action']!r} "
					f"roi=({roi['x']},"
					f"{roi['y']},"
					f"{roi['width']},"
					f"{roi['height']})"
				)
			)

		log_lines.extend(
			[
				"",
				"BOARD ROI",
			]
		)

		for card in card_metadata[
			"board"
		]:
			roi = card["roi"]

			log_lines.append(
				(
					f"B{card['index']} "
					f"value={card['value']} "
					f"roi=({roi['x']},"
					f"{roi['y']},"
					f"{roi['width']},"
					f"{roi['height']}) "
					f"center=({roi['center_x']},"
					f"{roi['center_y']})"
				)
			)

		log_lines.extend(
			[
				"",
				"HERO ROI",
			]
		)

		for card in card_metadata[
			"hero"
		]:
			roi = card["roi"]

			log_lines.append(
				(
					f"H{card['index']} "
					f"value={card['value']} "
					f"roi=({roi['x']},"
					f"{roi['y']},"
					f"{roi['width']},"
					f"{roi['height']}) "
					f"center=({roi['center_x']},"
					f"{roi['center_y']})"
				)
			)

		with open(
			output / "capture.log",
			"w",
			encoding="utf-8",
		) as file:
			file.write(
				"\n".join(
					log_lines
				)
			)

		print(
			f"[CAPTURE] Saved: {output} "
			f"players={len(players)} "
			f"board={board_values} "
			f"hero={hero_values}"
		)

		return output
