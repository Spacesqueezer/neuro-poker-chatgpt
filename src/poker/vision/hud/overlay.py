\
from __future__ import annotations

from dataclasses import dataclass
import ctypes
import ctypes.wintypes
import os
import queue
import threading
import time

from poker.vision.debug.windows_capture import (
	exclude_from_capture,
)
from poker.vision.hud.manual_identity import (
	MANUAL_IDENTITIES,
)
from poker.vision.tracking.window_geometry import (
	PokerDomWindowWatcher,
)


OVERLAY_WINDOW_NAME = (
	"Neuro Poker HUD Overlay"
)

WM_NCHITTEST = 0x0084
HTCLIENT = 1
HTTRANSPARENT = -1
GWL_WNDPROC = -4


@dataclass(frozen=True)
class OverlayPlayer:
	index: int
	rect: tuple[int, int, int, int]
	name: str
	raw_name: str
	action: str
	is_hero: bool
	confidence: float
	identity_pending: bool
	name_source: str


@dataclass(frozen=True)
class OverlaySnapshot:
	table_width: int
	table_height: int
	players: tuple[OverlayPlayer, ...]
	street: str
	pot: str
	board: tuple[str, ...]
	hero: tuple[str, ...]
	is_my_turn: bool
	fps: float


class PokerHudOverlay:
	def __init__(self):
		self._queue = queue.Queue(
			maxsize=2
		)

		self._stop = threading.Event()
		self._thread = None
		self._enabled = (
			os.name == "nt"
		)

	def start(self):
		if not self._enabled:
			return

		if (
			self._thread is not None
			and self._thread.is_alive()
		):
			return

		self._thread = threading.Thread(
			target=self._run,
			name="PokerHudOverlay",
			daemon=True,
		)

		self._thread.start()

	def close(self):
		self._stop.set()

	def update(
		self,
		table_preview,
		players,
		board_values,
		hero_values,
		vision_state,
		fps,
	):
		if not self._enabled:
			return

		if (
			table_preview is None
			or not hasattr(
				table_preview,
				"shape",
			)
			or len(
				table_preview.shape
			) < 2
		):
			return

		height, width = (
			table_preview.shape[:2]
		)

		if (
			width <= 0
			or height <= 0
		):
			return

		rows = []

		for player in (
			players or []
		):
			panel = getattr(
				player,
				"panel",
				None,
			)

			rect = getattr(
				panel,
				"rect",
				None,
			)

			if (
				not rect
				or len(rect) != 4
			):
				continue

			rows.append(
				OverlayPlayer(
					index=int(
						getattr(
							player,
							"index",
							len(rows),
						)
					),
					rect=tuple(
						int(value)
						for value in rect
					),
					name=str(
						getattr(
							player,
							"name",
							"",
						)
						or ""
					),
					raw_name=str(
						getattr(
							player,
							"raw_name",
							"",
						)
						or ""
					),
					action=str(
						getattr(
							player,
							"action",
							"",
						)
						or ""
					),
					is_hero=bool(
						getattr(
							player,
							"is_hero",
							False,
						)
					),
					confidence=float(
						getattr(
							player,
							"confidence",
							0.0,
						)
						or 0.0
					),
					identity_pending=bool(
						getattr(
							player,
							"identity_pending",
							False,
						)
					),
					name_source=str(
						getattr(
							player,
							"name_source",
							"ocr",
						)
						or "ocr"
					),
				)
			)

		snapshot = OverlaySnapshot(
			table_width=int(
				width
			),
			table_height=int(
				height
			),
			players=tuple(
				rows
			),
			street=str(
				getattr(
					vision_state,
					"street_name",
					"",
				)
				or ""
			),
			pot=self._format_number(
				getattr(
					vision_state,
					"total_pot",
					None,
				)
			),
			board=tuple(
				str(value)
				for value in (
					board_values or []
				)
			),
			hero=tuple(
				str(value)
				for value in (
					hero_values or []
				)
			),
			is_my_turn=bool(
				getattr(
					vision_state,
					"is_my_turn",
					False,
				)
			),
			fps=float(
				fps or 0.0
			),
		)

		self.start()

		while True:
			try:
				self._queue.get_nowait()
			except queue.Empty:
				break

		try:
			self._queue.put_nowait(
				snapshot
			)
		except queue.Full:
			pass

	def _run(self):
		import tkinter as tk

		self._tk = tk
		self._root = tk.Tk()
		self._root.title(
			OVERLAY_WINDOW_NAME
		)

		self._transparent = "#010203"

		self._root.configure(
			bg=self._transparent
		)

		self._root.overrideredirect(
			True
		)

		self._root.attributes(
			"-topmost",
			True,
		)

		try:
			self._root.attributes(
				"-transparentcolor",
				self._transparent,
			)
		except Exception:
			pass

		self._canvas = tk.Canvas(
			self._root,
			bg=self._transparent,
			highlightthickness=0,
			borderwidth=0,
		)

		self._canvas.pack(
			fill="both",
			expand=True,
		)

		self._canvas.bind(
			"<Button-1>",
			self._on_click,
		)

		self._watcher = (
			PokerDomWindowWatcher()
		)

		self._name_hitboxes = []
		self._latest = None
		self._editor = None
		self._editor_seat = None

		self._install_hit_test()
		exclude_from_capture(
			OVERLAY_WINDOW_NAME
		)

		self._tick()
		self._root.mainloop()

	def _tick(self):
		if self._stop.is_set():
			try:
				self._root.destroy()
			except Exception:
				pass

			return

		latest = None

		while True:
			try:
				latest = (
					self._queue.get_nowait()
				)
			except queue.Empty:
				break

		if latest is not None:
			self._latest = latest

		if self._latest is not None:
			self._render(
				self._latest
			)

		self._root.after(
			33,
			self._tick,
		)

	def _render(
		self,
		snapshot,
	):
		_, rect = (
			self._watcher.poll()
		)

		if rect is None:
			self._root.withdraw()
			return

		self._root.deiconify()

		self._root.geometry(
			f"{rect.width}x{rect.height}"
			f"+{rect.left}+{rect.top}"
		)

		self._canvas.configure(
			width=rect.width,
			height=rect.height,
		)

		self._canvas.delete(
			"hud"
		)

		scale_x = (
			rect.width
			/ max(
				snapshot.table_width,
				1,
			)
		)

		scale_y = (
			rect.height
			/ max(
				snapshot.table_height,
				1,
			)
		)

		self._name_hitboxes = []

		for player in snapshot.players:
			self._draw_player(
				player,
				scale_x,
				scale_y,
				rect.width,
				rect.height,
			)

		self._draw_table_state(
			snapshot,
			rect.width,
			rect.height,
		)

	def _draw_player(
		self,
		player,
		scale_x,
		scale_y,
		window_width,
		window_height,
	):
		x1, y1, x2, y2 = (
			player.rect
		)

		x1 = int(
			x1 * scale_x
		)

		y1 = int(
			y1 * scale_y
		)

		x2 = int(
			x2 * scale_x
		)

		y2 = int(
			y2 * scale_y
		)

		panel_width = max(
			110,
			x2 - x1,
		)

		hud_width = min(
			245,
			max(
				165,
				int(
					panel_width * 1.20
				),
			),
		)

		hud_height = 68

		hud_x = x1

		if (
			hud_x + hud_width
			> window_width - 8
		):
			hud_x = max(
				8,
				x2 - hud_width,
			)

		hud_y = y1 - hud_height - 6

		if hud_y < 8:
			hud_y = min(
				window_height
				- hud_height
				- 8,
				y2 + 6,
			)

		status_color = (
			"#3cff73"
		)

		if not player.name:
			status_color = (
				"#9aa3ad"
			)
		elif player.identity_pending:
			status_color = (
				"#ffd43b"
			)
		elif (
			player.confidence < 0.72
			and player.name_source
			!= "manual"
		):
			status_color = (
				"#ffd43b"
			)

		if player.is_hero:
			status_color = (
				"#3cff73"
			)

		self._canvas.create_rectangle(
			hud_x,
			hud_y,
			hud_x + hud_width,
			hud_y + hud_height,
			fill="#10151b",
			outline=status_color,
			width=2,
			stipple="gray75",
			tags=("hud",),
		)

		name = (
			player.name
			or player.raw_name
			or "unknown"
		)

		source = (
			"M"
			if player.name_source
			== "manual"
			else "?"
			if player.identity_pending
			else "OCR"
		)

		confidence = (
			100
			if player.name_source
			== "manual"
			else int(
				max(
					0.0,
					min(
						1.0,
						player.confidence,
					),
				)
				* 100.0
			)
		)

		name_text = (
			f"{name}  [{source}]"
		)

		self._canvas.create_text(
			hud_x + 8,
			hud_y + 13,
			anchor="w",
			text=name_text,
			fill=status_color,
			font=(
				"Segoe UI",
				10,
				"bold",
			),
			tags=("hud",),
		)

		line2 = (
			f"conf {confidence}%"
		)

		if player.action:
			line2 += (
				f"   {player.action.upper()}"
			)

		self._canvas.create_text(
			hud_x + 8,
			hud_y + 34,
			anchor="w",
			text=line2,
			fill="#e8edf2",
			font=(
				"Segoe UI",
				9,
			),
			tags=("hud",),
		)

		self._canvas.create_text(
			hud_x + 8,
			hud_y + 53,
			anchor="w",
			text=(
				"VPIP --   PFR --   3B --"
			),
			fill="#9aa3ad",
			font=(
				"Segoe UI",
				8,
			),
			tags=("hud",),
		)

		self._name_hitboxes.append(
			(
				(
					hud_x,
					hud_y,
					hud_x
					+ hud_width,
					hud_y + 25,
				),
				player,
			)
		)

	def _draw_table_state(
		self,
		snapshot,
		window_width,
		window_height,
	):
		text = (
			f"{snapshot.street.upper() or '-'}"
			f"   POT {snapshot.pot or '-'}"
			f"   FPS {snapshot.fps:.1f}"
		)

		if snapshot.board:
			text += (
				"   BOARD "
				+ " ".join(
					snapshot.board
				)
			)

		if snapshot.hero:
			text += (
				"   HERO "
				+ " ".join(
					snapshot.hero
				)
			)

		if snapshot.is_my_turn:
			text += "   YOUR TURN"

		width = min(
			window_width - 24,
			max(
				340,
				9 * len(text),
			),
		)

		x1 = max(
			12,
			(
				window_width
				- width
			)
			// 2,
		)

		y1 = 12

		self._canvas.create_rectangle(
			x1,
			y1,
			x1 + width,
			y1 + 34,
			fill="#10151b",
			outline=(
				"#3cff73"
				if snapshot.is_my_turn
				else "#5c6772"
			),
			width=2,
			stipple="gray75",
			tags=("hud",),
		)

		self._canvas.create_text(
			x1 + 10,
			y1 + 17,
			anchor="w",
			text=text,
			fill="#f4f7fa",
			font=(
				"Segoe UI",
				9,
				"bold",
			),
			tags=("hud",),
		)

	def _on_click(
		self,
		event,
	):
		for rect, player in (
			self._name_hitboxes
		):
			x1, y1, x2, y2 = rect

			if (
				x1 <= event.x <= x2
				and y1 <= event.y <= y2
			):
				self._open_editor(
					player,
					x1,
					y2 + 4,
				)
				return

	def _open_editor(
		self,
		player,
		x,
		y,
	):
		if self._editor is not None:
			try:
				self._editor.destroy()
			except Exception:
				pass

		self._editor_seat = (
			player.index
		)

		editor = self._tk.Toplevel(
			self._root
		)

		editor.title(
			"Confirm nickname"
		)

		editor.attributes(
			"-topmost",
			True,
		)

		editor.configure(
			bg="#10151b"
		)

		root_x = (
			self._root.winfo_rootx()
		)

		root_y = (
			self._root.winfo_rooty()
		)

		editor.geometry(
			f"310x92"
			f"+{root_x + x}"
			f"+{root_y + y}"
		)

		label = self._tk.Label(
			editor,
			text=(
				f"Seat {player.index}: "
				f"OCR {player.raw_name or '-'}"
			),
			bg="#10151b",
			fg="#dfe6ed",
			anchor="w",
		)

		label.pack(
			fill="x",
			padx=8,
			pady=(
				8,
				3,
			),
		)

		entry = self._tk.Entry(
			editor,
			font=(
				"Segoe UI",
				11,
			),
		)

		entry.pack(
			fill="x",
			padx=8,
		)

		entry.insert(
			0,
			player.name
			or player.raw_name
			or "",
		)

		entry.select_range(
			0,
			"end",
		)

		entry.focus_force()

		status = self._tk.Label(
			editor,
			text=(
				"Enter = истина, Esc = отмена"
			),
			bg="#10151b",
			fg="#9aa3ad",
			anchor="w",
		)

		status.pack(
			fill="x",
			padx=8,
			pady=4,
		)

		def confirm(
			event=None,
		):
			try:
				MANUAL_IDENTITIES.set(
					player.index,
					entry.get(),
				)
			except ValueError as error:
				status.configure(
					text=str(error),
					fg="#ff5d67",
				)
				return

			editor.destroy()
			self._editor = None
			self._editor_seat = None

		def cancel(
			event=None,
		):
			editor.destroy()
			self._editor = None
			self._editor_seat = None

		entry.bind(
			"<Return>",
			confirm,
		)

		entry.bind(
			"<Escape>",
			cancel,
		)

		editor.protocol(
			"WM_DELETE_WINDOW",
			cancel,
		)

		self._editor = editor

	def _install_hit_test(self):
		if os.name != "nt":
			return

		try:
			self._root.update_idletasks()

			hwnd = int(
				self._root.winfo_id()
			)

			parent = (
				ctypes.windll.user32
				.GetParent(
					hwnd
				)
			)

			if parent:
				hwnd = int(
					parent
				)

			self._hwnd = hwnd

			long_ptr = (
				ctypes.c_ssize_t
			)

			WNDPROC = (
				ctypes.WINFUNCTYPE(
					long_ptr,
					ctypes.wintypes.HWND,
					ctypes.wintypes.UINT,
					ctypes.wintypes.WPARAM,
					ctypes.wintypes.LPARAM,
				)
			)

			user32 = ctypes.windll.user32

			user32.SetWindowLongPtrW.restype = (
				long_ptr
			)

			user32.SetWindowLongPtrW.argtypes = [
				ctypes.wintypes.HWND,
				ctypes.c_int,
				long_ptr,
			]

			user32.CallWindowProcW.restype = (
				long_ptr
			)

			self._old_wndproc = (
				user32.GetWindowLongPtrW(
					hwnd,
					GWL_WNDPROC,
				)
			)

			@WNDPROC
			def wndproc(
				window,
				message,
				wparam,
				lparam,
			):
				if message == WM_NCHITTEST:
					x = ctypes.c_short(
						lparam & 0xFFFF
					).value

					y = ctypes.c_short(
						(
							lparam >> 16
						)
						& 0xFFFF
					).value

					point = (
						ctypes.wintypes.POINT(
							x,
							y,
						)
					)

					user32.ScreenToClient(
						window,
						ctypes.byref(
							point
						),
					)

					if self._is_interactive_point(
						point.x,
						point.y,
					):
						return HTCLIENT

					return HTTRANSPARENT

				return user32.CallWindowProcW(
					self._old_wndproc,
					window,
					message,
					wparam,
					lparam,
				)

			self._wndproc = wndproc

			user32.SetWindowLongPtrW(
				hwnd,
				GWL_WNDPROC,
				ctypes.cast(
					wndproc,
					ctypes.c_void_p,
				).value,
			)
		except Exception:
			# Fallback: overlay remains visible.
			# The editor can still be used, but selective hit-test
			# may not be available on an unusual Tk/Windows build.
			pass

	def _is_interactive_point(
		self,
		x,
		y,
	):
		for rect, _ in (
			self._name_hitboxes
		):
			x1, y1, x2, y2 = rect

			if (
				x1 <= x <= x2
				and y1 <= y <= y2
			):
				return True

		return False

	@staticmethod
	def _format_number(
		value,
	):
		if value is None:
			return ""

		try:
			return (
				f"{float(value):.2f}"
				.rstrip("0")
				.rstrip(".")
			)
		except Exception:
			return str(
				value
			)
