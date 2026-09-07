from __future__ import annotations

import time

import cv2
import numpy as np


BG = (24, 24, 24)
SECTION_BG = (32, 32, 32)
BORDER = (62, 62, 62)
TEXT = (230, 230, 230)
MUTED = (150, 150, 150)
GREEN = (90, 220, 110)
YELLOW = (80, 210, 245)
RED = (80, 80, 240)
CYAN = (230, 200, 80)
HERO = (100, 235, 120)


class ScannerDashboard:
	def __init__(self):
		self.event_text = "Vision starting..."
		self.event_kind = "info"
		self.event_until = 0.0

		self.output_width = 1500
		self.output_height = 860
		self.preview_width = 870
		self.panel_width = 630
		self.ui_scale = 1.0

	def set_event(
		self,
		text,
		kind="info",
		duration=4.0,
	):
		self.event_text = str(text)
		self.event_kind = kind
		self.event_until = (
			time.monotonic()
			+ max(
				0.0,
				duration,
			)
		)

	def render(
		self,
		table_preview,
		*,
		screen_size=None,
		locked,
		fps,
		panels,
		players,
		board_values,
		hero_values,
		vision_state,
		action_state,
		panel_worker_busy=False,
		ocr_worker_busy=False,
		card_worker_busy=False,
		hero_locked=False,
		board_box_count=0,
		hero_box_count=0,
	):
		self._configure_layout(
			screen_size,
			table_preview,
		)

		table_preview = self._fit_preview(
			table_preview
		)

		height = self.output_height

		panel = np.full(
			(
				height,
				self.panel_width,
				3,
			),
			BG,
			dtype=np.uint8,
		)

		y = 22

		y = self._header(
			panel,
			y,
			locked=locked,
			fps=fps,
			panel_count=len(
				panels or []
			),
		)

		y = self._hand_section(
			panel,
			y,
			vision_state=vision_state,
			board_values=board_values,
			hero_values=hero_values,
		)

		y = self._players_section(
			panel,
			y,
			players=players,
			panels=panels,
		)

		y = self._actions_section(
			panel,
			y,
			vision_state=vision_state,
			action_state=action_state,
		)

		y = self._diagnostics_section(
			panel,
			y,
			panel_worker_busy=panel_worker_busy,
			ocr_worker_busy=ocr_worker_busy,
			card_worker_busy=card_worker_busy,
			hero_locked=hero_locked,
			board_box_count=board_box_count,
			hero_box_count=hero_box_count,
			board_values=board_values,
			hero_values=hero_values,
		)

		self._footer(
			panel,
			height,
		)

		return np.hstack(
			(
				table_preview,
				panel,
			)
		)

	def render_searching(
		self,
		frame,
		fps,
		screen_size=None,
	):
		preview = frame.copy()

		cv2.putText(
			preview,
			"SEARCHING TABLE",
			(24, 42),
			cv2.FONT_HERSHEY_SIMPLEX,
			0.9,
			RED,
			2,
			cv2.LINE_AA,
		)

		return self.render(
			preview,
			screen_size=screen_size,
			locked=False,
			fps=fps,
			panels=[],
			players=[],
			board_values=[],
			hero_values=[],
			vision_state=None,
			action_state=None,
		)

	def _header(
		self,
		panel,
		y,
		*,
		locked,
		fps,
		panel_count,
	):
		self._text(
			panel,
			"NEURO POKER / VISION",
			18,
			y,
			scale=0.72,
			color=TEXT,
			thickness=2,
		)

		y += 28

		status_color = (
			GREEN
			if locked
			else RED
		)

		status = (
			"TABLE LOCKED"
			if locked
			else "SEARCHING TABLE"
		)

		self._pill(
			panel,
			18,
			y,
			status,
			status_color,
		)

		self._text(
			panel,
			f"FPS {fps:.1f}",
			210,
			y + 18,
			scale=0.62,
			color=TEXT,
		)

		self._text(
			panel,
			f"Panels {panel_count}",
			285,
			y + 18,
			scale=0.56,
			color=MUTED,
		)

		y += 46

		return y

	def _hand_section(
		self,
		panel,
		y,
		*,
		vision_state,
		board_values,
		hero_values,
	):
		start = y

		street = self._state_value(
			vision_state,
			"street_name",
			"-",
		)

		pot = self._state_value(
			vision_state,
			"total_pot",
			None,
		)

		is_my_turn = bool(
			self._state_value(
				vision_state,
				"is_my_turn",
				False,
			)
		)

		y = self._section_title(
			panel,
			y,
			"HAND",
		)

		self._key_value(
			panel,
			y,
			"Street",
			str(
				street or "-"
			).upper(),
			value_color=YELLOW,
		)

		y += 25

		pot_text = (
			"-"
			if pot is None
			else self._number(
				pot
			)
		)

		self._key_value(
			panel,
			y,
			"Pot",
			pot_text,
		)

		y += 27

		self._text(
			panel,
			"Hero",
			20,
			y,
			scale=0.56,
			color=MUTED,
		)

		self._cards(
			panel,
			self._s(112),
			y - self._s(20),
			hero_values,
			empty_count=2,
			accent=HERO,
		)

		y += 34

		self._text(
			panel,
			"Board",
			20,
			y,
			scale=0.56,
			color=MUTED,
		)

		self._cards(
			panel,
			self._s(112),
			y - self._s(20),
			board_values,
			empty_count=5,
			accent=CYAN,
		)

		y += 38

		turn_text = (
			"YOUR TURN"
			if is_my_turn
			else "waiting"
		)

		turn_color = (
			GREEN
			if is_my_turn
			else MUTED
		)

		self._pill(
			panel,
			18,
			y,
			turn_text,
			turn_color,
			width=128,
		)

		y += 42

		self._section_box(
			panel,
			start,
			y - start,
		)

		return y + 8

	def _players_section(
		self,
		panel,
		y,
		*,
		players,
		panels,
	):
		start = y

		y = self._section_title(
			panel,
			y,
			"PLAYERS",
		)

		rows = list(
			players or []
		)

		if not rows and panels:
			rows = [
				None
				for _ in panels
			]

		if not rows:
			self._text(
				panel,
				"No players yet",
				20,
				y,
				scale=0.54,
				color=MUTED,
			)

			y += 24
		else:
			max_rows = 9

			for index, player in enumerate(
				rows[:max_rows]
			):
				if player is None:
					name = (
						f"player_{index}"
					)

					action = ""
					is_hero = False
				else:
					name = (
						getattr(
							player,
							"name",
							"",
						)
						or f"player_{index}"
					)

					action = (
						getattr(
							player,
							"action",
							None,
						)
						or ""
					)

					is_hero = bool(
						getattr(
							player,
							"is_hero",
							False,
						)
					)

				prefix = (
					"H"
					if is_hero
					else str(
						index + 1
					)
				)

				prefix_color = (
					HERO
					if is_hero
					else MUTED
				)

				self._text(
					panel,
					prefix,
					20,
					y,
					scale=0.56,
					color=prefix_color,
					thickness=(
						2
						if is_hero
						else 1
					),
				)

				self._text(
					panel,
					self._clip(
						name,
						22,
					),
					48,
					y,
					scale=0.58,
					color=(
						HERO
						if is_hero
						else TEXT
					),
					thickness=(
						2
						if is_hero
						else 1
					),
				)

				if action:
					self._text(
						panel,
						self._clip(
							action.upper(),
							10,
						),
						286,
						y,
						scale=0.49,
						color=YELLOW,
					)

				y += 23

			if len(rows) > max_rows:
				self._text(
					panel,
					f"+{len(rows) - max_rows} more",
					20,
					y,
					scale=0.50,
					color=MUTED,
				)

				y += 21

		self._section_box(
			panel,
			start,
			y - start + 7,
		)

		return y + 15

	def _actions_section(
		self,
		panel,
		y,
		*,
		vision_state,
		action_state,
	):
		start = y

		y = self._section_title(
			panel,
			y,
			"ACTIONS",
		)

		action_pairs = [
			(
				"FOLD",
				"can_fold",
			),
			(
				"CHECK",
				"can_check",
			),
			(
				"CALL",
				"can_call",
			),
			(
				"BET",
				"can_bet",
			),
			(
				"RAISE",
				"can_raise",
			),
			(
				"ALL IN",
				"can_all_in",
			),
		]

		x = 20
		row_y = y

		for label, field in action_pairs:
			enabled = bool(
				self._state_value(
					vision_state,
					field,
					False,
				)
			)

			color = (
				GREEN
				if enabled
				else (65, 65, 65)
			)

			width = 94

			self._pill(
				panel,
				x,
				row_y,
				label,
				color,
				width=width,
			)

			x += width + 8

			if x + width > self.panel_width - self._s(22):
				x = 20
				row_y += 35

		y = row_y + 40

		buttons = (
			getattr(
				action_state,
				"buttons",
				[],
			)
			if action_state is not None
			else []
		)

		if buttons:
			detected = ", ".join(
				self._clip(
					getattr(
						button,
						"action",
						"?",
					),
					12,
				)
				for button in buttons
			)

			self._text(
				panel,
				f"Detected: {detected}",
				20,
				y,
				scale=0.49,
				color=MUTED,
			)

			y += 22

		self._section_box(
			panel,
			start,
			y - start + 6,
		)

		return y + 14

	def _diagnostics_section(
		self,
		panel,
		y,
		*,
		panel_worker_busy,
		ocr_worker_busy,
		card_worker_busy,
		hero_locked,
		board_box_count,
		hero_box_count,
		board_values,
		hero_values,
	):
		if y > panel.shape[0] - 150:
			return y

		start = y

		y = self._section_title(
			panel,
			y,
			"VISION",
		)

		panel_worker = (
			"busy"
			if panel_worker_busy
			else "idle"
		)

		ocr_worker = (
			"busy"
			if ocr_worker_busy
			else "idle"
		)

		self._key_value(
			panel,
			y,
			"Panel worker",
			panel_worker,
			value_color=(
				YELLOW
				if panel_worker_busy
				else MUTED
			),
		)

		y += 22

		self._key_value(
			panel,
			y,
			"Name worker",
			ocr_worker,
			value_color=(
				YELLOW
				if ocr_worker_busy
				else MUTED
			),
		)

		y += 22

		card_worker = (
			"busy"
			if card_worker_busy
			else "idle"
		)

		self._key_value(
			panel,
			y,
			"Card worker",
			card_worker,
			value_color=(
				YELLOW
				if card_worker_busy
				else MUTED
			),
		)

		y += 22

		self._key_value(
			panel,
			y,
			"HERO lock",
			(
				"LOCKED"
				if hero_locked
				else "searching"
			),
			value_color=(
				GREEN
				if hero_locked
				else YELLOW
			),
		)

		y += 22

		self._key_value(
			panel,
			y,
			"Card boxes",
			f"B:{board_box_count} H:{hero_box_count}",
		)

		y += 22

		self._key_value(
			panel,
			y,
			"Cards read",
			f"B:{len(board_values or [])} H:{len(hero_values or [])}",
		)

		y += 28

		self._section_box(
			panel,
			start,
			y - start,
		)

		return y + 8

	def _footer(
		self,
		panel,
		height,
	):
		y = max(
			12,
			height - 82,
		)

		cv2.line(
			panel,
			(16, y - 10),
			(
				self.panel_width - self._s(18),
				y - 10,
			),
			BORDER,
			1,
		)

		event_color = {
			"ok": GREEN,
			"warning": YELLOW,
			"error": RED,
			"info": MUTED,
		}.get(
			self.event_kind,
			MUTED,
		)

		if (
			self.event_until
			and time.monotonic()
			> self.event_until
		):
			event_text = "Running"
			event_color = MUTED
		else:
			event_text = (
				self.event_text
				or "Running"
			)

		self._text(
			panel,
			self._clip(
				event_text,
				47,
			),
			18,
			y + 8,
			scale=0.50,
			color=event_color,
		)

		self._text(
			panel,
			"Q quit   R re-lock   S / Ы capture",
			18,
			y + 34,
			scale=0.49,
			color=MUTED,
		)

	def _section_title(
		self,
		panel,
		y,
		title,
	):
		self._text(
			panel,
			title,
			18,
			y + 17,
			scale=0.58,
			color=MUTED,
			thickness=2,
		)

		return y + 35

	def _section_box(
		self,
		panel,
		y,
		height,
	):
		cv2.rectangle(
			panel,
			(10, y),
			(
				self.panel_width - self._s(11),
				min(
					panel.shape[0] - 1,
					y + height,
				),
			),
			BORDER,
			1,
		)

	def _key_value(
		self,
		panel,
		y,
		key,
		value,
		value_color=TEXT,
	):
		self._text(
			panel,
			key,
			20,
			y,
			scale=0.54,
			color=MUTED,
		)

		self._text(
			panel,
			self._clip(
				str(value),
				20,
			),
			150,
			y,
			scale=0.58,
			color=value_color,
		)

	def _cards(
		self,
		panel,
		x,
		y,
		values,
		empty_count,
		accent,
	):
		values = list(
			values or []
		)

		count = max(
			empty_count,
			len(values),
		)

		for index in range(count):
			value = (
				values[index]
				if index < len(values)
				else ""
			)

			self._card(
				panel,
				x + index * 52,
				y,
				value,
				accent,
			)

	def _card(
		self,
		panel,
		x,
		y,
		value,
		accent,
	):
		width = 44
		height = 27

		if not value:
			cv2.rectangle(
				panel,
				(x, y),
				(
					x + width,
					y + height,
				),
				(44, 44, 44),
				-1,
			)

			cv2.rectangle(
				panel,
				(x, y),
				(
					x + width,
					y + height,
				),
				BORDER,
				1,
			)

			self._text(
				panel,
				"-",
				x + 17,
				y + 19,
				scale=0.56,
				color=MUTED,
			)

			return

		value = str(
			value
		)

		rank = (
			value[0].upper()
			if value
			else "?"
		)

		suit = (
			value[1].lower()
			if len(value) >= 2
			else ""
		)

		is_red = suit in {
			"h",
			"d",
		}

		card_color = (
			(55, 55, 225)
			if is_red
			else (18, 18, 18)
		)

		cv2.rectangle(
			panel,
			(x, y),
			(
				x + width,
				y + height,
			),
			(238, 238, 238),
			-1,
		)

		cv2.rectangle(
			panel,
			(x, y),
			(
				x + width,
				y + height,
			),
			accent,
			1,
		)

		self._text(
			panel,
			rank,
			x + 5,
			y + 19,
			scale=0.58,
			color=card_color,
			thickness=2,
		)

		self._draw_suit(
			panel,
			x + 31,
			y + 14,
			suit,
			card_color,
		)

	def _draw_suit(
		self,
		panel,
		x,
		y,
		suit,
		color,
	):
		radius = max(
			2,
			self._s(3),
		)

		if suit == "h":
			cv2.circle(
				panel,
				(
					x - radius,
					y - radius,
				),
				radius,
				color,
				-1,
			)

			cv2.circle(
				panel,
				(
					x + radius,
					y - radius,
				),
				radius,
				color,
				-1,
			)

			points = np.array(
				[
					[
						x - radius * 2,
						y - radius,
					],
					[
						x + radius * 2,
						y - radius,
					],
					[
						x,
						y + radius * 3,
					],
				],
				dtype=np.int32,
			)

			cv2.fillConvexPoly(
				panel,
				points,
				color,
			)

		elif suit == "d":
			points = np.array(
				[
					[
						x,
						y - radius * 2,
					],
					[
						x + radius * 2,
						y,
					],
					[
						x,
						y + radius * 2,
					],
					[
						x - radius * 2,
						y,
					],
				],
				dtype=np.int32,
			)

			cv2.fillConvexPoly(
				panel,
				points,
				color,
			)

		elif suit == "c":
			cv2.circle(
				panel,
				(
					x,
					y - radius,
				),
				radius,
				color,
				-1,
			)

			cv2.circle(
				panel,
				(
					x - radius,
					y + radius // 2,
				),
				radius,
				color,
				-1,
			)

			cv2.circle(
				panel,
				(
					x + radius,
					y + radius // 2,
				),
				radius,
				color,
				-1,
			)

			cv2.rectangle(
				panel,
				(
					x - 1,
					y + radius // 2,
				),
				(
					x + 1,
					y + radius * 2,
				),
				color,
				-1,
			)

		elif suit == "s":
			points = np.array(
				[
					[
						x,
						y - radius * 3,
					],
					[
						x - radius * 2,
						y,
					],
					[
						x + radius * 2,
						y,
					],
				],
				dtype=np.int32,
			)

			cv2.fillConvexPoly(
				panel,
				points,
				color,
			)

			cv2.circle(
				panel,
				(
					x - radius,
					y,
				),
				radius,
				color,
				-1,
			)

			cv2.circle(
				panel,
				(
					x + radius,
					y,
				),
				radius,
				color,
				-1,
			)

			cv2.rectangle(
				panel,
				(
					x - 1,
					y,
				),
				(
					x + 1,
					y + radius * 2,
				),
				color,
				-1,
			)

	def _pill(
		self,
		panel,
		x,
		y,
		text,
		color,
		width=None,
	):
		if width is None:
			width = max(
				92,
				18 + len(
					text
				) * 8,
			)

		height = 27

		cv2.rectangle(
			panel,
			(x, y),
			(
				x + width,
				y + height,
			),
			(42, 42, 42),
			-1,
		)

		cv2.rectangle(
			panel,
			(x, y),
			(
				x + width,
				y + height,
			),
			color,
			1,
		)

		self._text(
			panel,
			text,
			x + 8,
			y + 18,
			scale=0.50,
			color=color,
			thickness=1,
		)

	def _text(
		self,
		panel,
		text,
		x,
		y,
		*,
		scale=0.56,
		color=TEXT,
		thickness=1,
	):
		cv2.putText(
			panel,
			str(text),
			(
				int(x),
				int(y),
			),
			cv2.FONT_HERSHEY_SIMPLEX,
			scale * self.ui_scale,
			color,
			thickness,
			cv2.LINE_AA,
		)


	def _configure_layout(
		self,
		screen_size,
		table_preview,
	):
		if screen_size:
			screen_width = max(
				800,
				int(screen_size[0]),
			)
			screen_height = max(
				600,
				int(screen_size[1]),
			)
		elif table_preview is not None:
			screen_height, screen_width = (
				table_preview.shape[:2]
			)
		else:
			screen_width = 1920
			screen_height = 1080

		self.output_width = self._clamp(
			int(screen_width * 0.78),
			1420,
			2200,
		)

		self.output_height = self._clamp(
			int(screen_height * 0.80),
			800,
			1120,
		)

		panel_ratio = (
			0.43
			if self.output_width >= 1800
			else 0.40
		)

		self.panel_width = int(
			self.output_width
			* panel_ratio
		)

		self.preview_width = (
			self.output_width
			- self.panel_width
		)

		self.ui_scale = max(
			1.0,
			min(
				1.30,
				self.output_height / 860.0,
			),
		)

	def _fit_preview(
		self,
		table_preview,
	):
		canvas = np.full(
			(
				self.output_height,
				self.preview_width,
				3,
			),
			(12, 12, 12),
			dtype=np.uint8,
		)

		if (
			table_preview is None
			or table_preview.size == 0
		):
			return canvas

		height, width = table_preview.shape[:2]
		padding = self._s(18)

		max_width = max(
			1,
			self.preview_width - padding * 2,
		)

		max_height = max(
			1,
			self.output_height - padding * 2,
		)

		scale = min(
			max_width / max(width, 1),
			max_height / max(height, 1),
		)

		display_width = max(
			1,
			int(round(width * scale)),
		)

		display_height = max(
			1,
			int(round(height * scale)),
		)

		resized = cv2.resize(
			table_preview,
			(
				display_width,
				display_height,
			),
			interpolation=(
				cv2.INTER_AREA
				if scale < 1.0
				else cv2.INTER_LINEAR
			),
		)

		x = (
			self.preview_width
			- display_width
		) // 2

		y = (
			self.output_height
			- display_height
		) // 2

		canvas[
			y:y + display_height,
			x:x + display_width,
		] = resized

		return canvas

	def _s(
		self,
		value,
	):
		return max(
			1,
			int(
				round(
					value * self.ui_scale
				)
			),
		)

	def _clamp(
		self,
		value,
		minimum,
		maximum,
	):
		return max(
			minimum,
			min(
				maximum,
				value,
			),
		)

	def _state_value(
		self,
		state,
		field,
		default,
	):
		if state is None:
			return default

		if hasattr(
			state,
			field,
		):
			return getattr(
				state,
				field,
			)

		if hasattr(
			state,
			"to_dict",
		):
			try:
				return state.to_dict().get(
					field,
					default,
				)
			except Exception:
				return default

		return default

	def _clip(
		self,
		value,
		max_length,
	):
		value = str(value)

		if len(value) <= max_length:
			return value

		return (
			value[
				:max(
					1,
					max_length - 3,
				)
			]
			+ "..."
		)

	def _number(
		self,
		value,
	):
		try:
			number = float(
				value
			)
		except (
			TypeError,
			ValueError,
		):
			return str(value)

		if number.is_integer():
			return str(
				int(number)
			)

		return f"{number:.2f}"
