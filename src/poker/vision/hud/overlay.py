
from __future__ import annotations

import os
import queue
import threading

from dataclasses import dataclass


@dataclass(frozen=True)
class OverlaySnapshot:
	table_width: int
	table_height: int
	players: tuple
	street: str
	pot: str
	board: tuple
	hero: tuple
	is_my_turn: bool
	fps: float


class PokerHudOverlay:
	"""
	Stable HUD overlay.

	No custom WndProc hooks.
	No SetWindowDisplayAffinity.
	No capture exclusion.

	The goal of this version is to keep the poker client
	rendering and capture pipeline alive.
	"""

	def __init__(self):
		self._queue = queue.Queue(maxsize=2)
		self._stop = threading.Event()
		self._thread = None
		self._enabled = os.name == "nt"

	def start(self):
		if not self._enabled:
			return

		if self._thread and self._thread.is_alive():
			return

		self._thread = threading.Thread(
			target=self._run,
			name="PokerHudOverlay",
			daemon=True,
		)
		self._thread.start()

	def close(self):
		self._stop.set()

	def update(self, snapshot):
		if not self._enabled:
			return

		while True:
			try:
				self._queue.get_nowait()
			except queue.Empty:
				break

		try:
			self._queue.put_nowait(snapshot)
		except queue.Full:
			pass

	def _run(self):
		import tkinter as tk

		root = tk.Tk()
		root.overrideredirect(True)
		root.attributes("-topmost", True)

		canvas = tk.Canvas(
			root,
			bg="black",
			highlightthickness=0,
		)
		canvas.pack(fill="both", expand=True)

		self._configure_click_through(root)

		def tick():
			if self._stop.is_set():
				root.destroy()
				return

			try:
				snapshot = self._queue.get_nowait()
				canvas.delete("all")
				canvas.create_text(
					20,
					20,
					anchor="nw",
					text=(
						f"{snapshot.street} "
						f"POT {snapshot.pot} "
						f"FPS {snapshot.fps:.1f}"
					),
					fill="white",
				)
			except queue.Empty:
				pass

			root.after(33, tick)

		tick()
		root.mainloop()

	def _configure_click_through(self, root):
		if os.name != "nt":
			return

		try:
			import ctypes

			user32 = ctypes.windll.user32

			hwnd = int(
				root.winfo_id()
			)

			style = user32.GetWindowLongW(
				hwnd,
				-20,
			)

			user32.SetWindowLongW(
				hwnd,
				-20,
				style
				| 0x00080000  # WS_EX_LAYERED
				| 0x00000020  # WS_EX_TRANSPARENT
				| 0x08000000  # WS_EX_NOACTIVATE
				| 0x00000080, # WS_EX_TOOLWINDOW
			)

		except Exception:
			pass
