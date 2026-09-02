from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import tkinter as tk
from tkinter import ttk

import cv2
from PIL import Image, ImageTk

from poker.vision.project_paths import find_project_root
from poker.vision.recognition.name_character_templates import (
	accept_segmented_sample,
	save_name_template,
	segment_known_name,
)
from poker.vision.recognition.name_template_predictor import (
	CharacterTemplatePredictor,
	LOWER_NAME_CHARS,
)
from poker.vision.ocr.name_reader import read_player_name


WINDOW_TITLE = "Neuro Poker — Разметка никнеймов"
WINDOW_WIDTH = 1360
WINDOW_HEIGHT = 860
SAMPLE_MAX_WIDTH = 900
SAMPLE_MAX_HEIGHT = 470
SEGMENT_BOX_WIDTH = 62
SEGMENT_BOX_HEIGHT = 108
SEGMENT_GAP = 8
DEBOUNCE_MS = 160
CHAR_READY_TARGET = 20
CHAR_GOOD_TARGET = 10
CHAR_MINIMUM_TARGET = 5


@dataclass
class ImageTransform:
	scale: float
	offset_x: int
	offset_y: int
	display_width: int
	display_height: int


class NameLabelerApp:
	def __init__(
		self,
		root: tk.Tk,
		project_root: Path,
		sample_paths: list[Path],
	):
		self.root = root
		self.project_root = project_root
		self.sample_paths = sample_paths
		self.predictor = CharacterTemplatePredictor(
			project_root
		)

		self.state_path = (
			project_root
			/ "captures"
			/ "name_labeler_state.json"
		)

		self.state = self._load_state()
		self.index = self._resolve_start_index()

		self.sample_path = None
		self.sample_image = None
		self.crop_rect = None
		self.segmented = None

		self.sample_photo = None
		self.segment_photos = []
		self.sample_transform = ImageTransform(
			scale=1.0,
			offset_x=0,
			offset_y=0,
			display_width=1,
			display_height=1,
		)

		self.drag_start = None
		self.drag_rect_id = None
		self.preview_job = None
		self.guess_job = None

		self.nickname_var = tk.StringVar()
		self.status_var = tk.StringVar()
		self.file_var = tk.StringVar()
		self.progress_var = tk.StringVar()
		self.crop_var = tk.StringVar()
		self.guess_var = tk.StringVar(
			value="Похоже на: —"
		)
		self.check_var = tk.StringVar(
			value="Проверка шаблонами: —"
		)

		self.dictionary_summary_var = tk.StringVar(
			value="Словарь: считаю..."
		)

		self.dictionary_counts = {}

		self.guess_value = ""
		self.placeholder_active = False
		self.placeholder_value = ""

		self._build_ui()
		self._bind_events()
		self._refresh_dictionary_progress()
		self._load_current_sample()

	def _build_ui(self):
		self.root.title(
			WINDOW_TITLE
		)

		self.root.geometry(
			f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}"
		)

		self.root.minsize(
			1080,
			700,
		)

		style = ttk.Style()

		try:
			style.theme_use(
				"vista"
			)
		except tk.TclError:
			pass

		style.configure(
			"Primary.TButton",
			font=(
				"Segoe UI",
				10,
				"bold",
			),
			padding=(
				12,
				8,
			),
		)

		main = ttk.Frame(
			self.root,
			padding=10,
		)

		main.pack(
			fill=tk.BOTH,
			expand=True,
		)

		main.columnconfigure(
			0,
			weight=1,
		)

		main.columnconfigure(
			1,
			weight=0,
		)

		main.rowconfigure(
			1,
			weight=1,
		)

		header = ttk.Frame(
			main
		)

		header.grid(
			row=0,
			column=0,
			columnspan=2,
			sticky="ew",
			pady=(0, 8),
		)

		header.columnconfigure(
			0,
			weight=1,
		)

		ttk.Label(
			header,
			text="Разметка никнеймов",
			font=(
				"Segoe UI",
				15,
				"bold",
			),
		).grid(
			row=0,
			column=0,
			sticky="w",
		)

		ttk.Label(
			header,
			textvariable=self.progress_var,
			font=(
				"Segoe UI",
				10,
			),
		).grid(
			row=0,
			column=1,
			sticky="e",
		)

		left = ttk.Frame(
			main
		)

		left.grid(
			row=1,
			column=0,
			sticky="nsew",
			padx=(0, 10),
		)

		left.columnconfigure(
			0,
			weight=1,
		)

		left.rowconfigure(
			1,
			weight=1,
		)

		ttk.Label(
			left,
			textvariable=self.file_var,
			font=(
				"Segoe UI",
				9,
			),
		).grid(
			row=0,
			column=0,
			sticky="w",
			pady=(0, 5),
		)

		sample_frame = ttk.LabelFrame(
			left,
			text="1. Sample / crop",
			padding=7,
		)

		sample_frame.grid(
			row=1,
			column=0,
			sticky="nsew",
		)

		sample_frame.columnconfigure(
			0,
			weight=1,
		)

		sample_frame.rowconfigure(
			0,
			weight=1,
		)

		self.sample_canvas = tk.Canvas(
			sample_frame,
			background="#151515",
			highlightthickness=0,
			cursor="crosshair",
		)

		self.sample_canvas.grid(
			row=0,
			column=0,
			sticky="nsew",
		)

		ttk.Label(
			sample_frame,
			textvariable=self.crop_var,
			font=(
				"Segoe UI",
				9,
			),
		).grid(
			row=1,
			column=0,
			sticky="w",
			pady=(5, 0),
		)

		preview_frame = ttk.LabelFrame(
			left,
			text="2. Проверка сегментов",
			padding=7,
		)

		preview_frame.grid(
			row=2,
			column=0,
			sticky="ew",
			pady=(8, 0),
		)

		preview_frame.columnconfigure(
			0,
			weight=1,
		)

		self.segment_canvas = tk.Canvas(
			preview_frame,
			height=132,
			background="#101010",
			highlightthickness=0,
		)

		self.segment_canvas.grid(
			row=0,
			column=0,
			sticky="ew",
		)

		scroll = ttk.Scrollbar(
			preview_frame,
			orient=tk.HORIZONTAL,
			command=self.segment_canvas.xview,
		)

		scroll.grid(
			row=1,
			column=0,
			sticky="ew",
			pady=(4, 0),
		)

		self.segment_canvas.configure(
			xscrollcommand=scroll.set
		)

		sidebar_outer = ttk.Frame(
			main,
			width=430,
		)

		sidebar_outer.grid(
			row=1,
			column=1,
			sticky="nsew",
		)

		sidebar_outer.grid_propagate(
			False
		)

		sidebar_outer.columnconfigure(
			0,
			weight=1,
		)

		sidebar_outer.rowconfigure(
			0,
			weight=1,
		)

		self.sidebar_canvas = tk.Canvas(
			sidebar_outer,
			highlightthickness=0,
			borderwidth=0,
		)

		self.sidebar_canvas.grid(
			row=0,
			column=0,
			sticky="nsew",
		)

		self.sidebar_scrollbar = ttk.Scrollbar(
			sidebar_outer,
			orient=tk.VERTICAL,
			command=self.sidebar_canvas.yview,
		)

		self.sidebar_scrollbar.grid(
			row=0,
			column=1,
			sticky="ns",
		)

		self.sidebar_canvas.configure(
			yscrollcommand=self.sidebar_scrollbar.set
		)

		sidebar = ttk.Frame(
			self.sidebar_canvas,
			padding=(4, 0, 8, 0),
		)

		self.sidebar_window = self.sidebar_canvas.create_window(
			(0, 0),
			window=sidebar,
			anchor="nw",
		)

		sidebar.columnconfigure(
			0,
			weight=1,
		)

		sidebar.bind(
			"<Configure>",
			self._on_sidebar_content_configure,
		)

		self.sidebar_canvas.bind(
			"<Configure>",
			self._on_sidebar_canvas_configure,
		)

		self.sidebar_canvas.bind_all(
			"<MouseWheel>",
			self._on_sidebar_mousewheel,
		)

		ttk.Label(
			sidebar,
			text="3. Правильный ник",
			font=(
				"Segoe UI",
				11,
				"bold",
			),
		).grid(
			row=0,
			column=0,
			sticky="w",
			pady=(0, 5),
		)

		self.nickname_entry = tk.Entry(
			sidebar,
			textvariable=self.nickname_var,
			font=(
				"Consolas",
				16,
			),
			relief=tk.SOLID,
			borderwidth=1,
		)

		self.nickname_entry.grid(
			row=1,
			column=0,
			sticky="ew",
		)

		guess_row = ttk.Frame(
			sidebar
		)

		guess_row.grid(
			row=2,
			column=0,
			sticky="ew",
			pady=(5, 4),
		)

		guess_row.columnconfigure(
			0,
			weight=1,
		)

		ttk.Label(
			guess_row,
			textvariable=self.guess_var,
			font=(
				"Segoe UI",
				9,
			),
			foreground="#666666",
		).grid(
			row=0,
			column=0,
			sticky="w",
		)

		self.guess_button = ttk.Button(
			guess_row,
			text="Вставить",
			command=self._insert_guess,
		)

		self.guess_button.grid(
			row=0,
			column=1,
			sticky="e",
		)

		ttk.Label(
			sidebar,
			textvariable=self.check_var,
			font=(
				"Segoe UI",
				9,
				"bold",
			),
			wraplength=370,
		).grid(
			row=3,
			column=0,
			sticky="w",
			pady=(4, 12),
		)

		self.accept_button = ttk.Button(
			sidebar,
			text="✓ Принять sample",
			style="Primary.TButton",
			command=self._accept_sample,
		)

		self.accept_button.grid(
			row=4,
			column=0,
			sticky="ew",
			pady=(0, 8),
		)

		ttk.Button(
			sidebar,
			text="Пропустить",
			command=self._skip_sample,
		).grid(
			row=5,
			column=0,
			sticky="ew",
			pady=(0, 8),
		)

		nav = ttk.Frame(
			sidebar
		)

		nav.grid(
			row=6,
			column=0,
			sticky="ew",
			pady=(0, 18),
		)

		nav.columnconfigure(
			0,
			weight=1,
		)

		nav.columnconfigure(
			1,
			weight=1,
		)

		self.previous_button = ttk.Button(
			nav,
			text="← Назад",
			command=self._previous_sample,
		)

		self.previous_button.grid(
			row=0,
			column=0,
			sticky="ew",
			padx=(0, 4),
		)

		self.next_button = ttk.Button(
			nav,
			text="Дальше →",
			command=self._next_sample,
		)

		self.next_button.grid(
			row=0,
			column=1,
			sticky="ew",
			padx=(4, 0),
		)

		ttk.Separator(
			sidebar,
			orient=tk.HORIZONTAL,
		).grid(
			row=7,
			column=0,
			sticky="ew",
			pady=(0, 14),
		)

		ttk.Label(
			sidebar,
			text="Crop",
			font=(
				"Segoe UI",
				10,
				"bold",
			),
		).grid(
			row=8,
			column=0,
			sticky="w",
			pady=(0, 6),
		)

		ttk.Button(
			sidebar,
			text="Auto crop",
			command=self._auto_crop,
		).grid(
			row=9,
			column=0,
			sticky="ew",
			pady=(0, 6),
		)

		ttk.Button(
			sidebar,
			text="Сбросить crop",
			command=self._reset_crop,
		).grid(
			row=10,
			column=0,
			sticky="ew",
			pady=(0, 6),
		)

		ttk.Button(
			sidebar,
			text="Очистить ник",
			command=self._clear_nickname,
		).grid(
			row=11,
			column=0,
			sticky="ew",
			pady=(0, 18),
		)

		ttk.Label(
			sidebar,
			text=(
				"Только нижний регистр.\n"
				"Разрешены: a-z, 0-9, _ и -\n\n"
				"Enter — принять\n"
				"Ctrl+S — пропустить\n"
				"Ctrl+← / Ctrl+→ — навигация\n"
				"Esc — выход"
			),
			font=(
				"Segoe UI",
				9,
			),
		).grid(
			row=12,
			column=0,
			sticky="w",
		)

		ttk.Separator(
			sidebar,
			orient=tk.HORIZONTAL,
		).grid(
			row=13,
			column=0,
			sticky="ew",
			pady=(14, 10),
		)

		ttk.Label(
			sidebar,
			text="Прогресс словаря",
			font=(
				"Segoe UI",
				10,
				"bold",
			),
		).grid(
			row=14,
			column=0,
			sticky="w",
			pady=(0, 4),
		)

		ttk.Label(
			sidebar,
			textvariable=self.dictionary_summary_var,
			font=(
				"Segoe UI",
				9,
			),
			wraplength=390,
			justify=tk.LEFT,
		).grid(
			row=15,
			column=0,
			sticky="w",
			pady=(0, 5),
		)

		dict_frame = ttk.Frame(
			sidebar
		)

		dict_frame.grid(
			row=16,
			column=0,
			sticky="ew",
		)

		dict_frame.columnconfigure(
			0,
			weight=1,
		)

		self.dictionary_canvas = tk.Canvas(
			dict_frame,
			height=260,
			background="#151515",
			highlightthickness=0,
		)

		self.dictionary_canvas.grid(
			row=0,
			column=0,
			sticky="ew",
		)

		status = ttk.Label(
			main,
			textvariable=self.status_var,
			anchor="w",
			padding=(8, 6),
			relief=tk.SUNKEN,
		)

		status.grid(
			row=2,
			column=0,
			columnspan=2,
			sticky="ew",
			pady=(8, 0),
		)

	def _on_sidebar_content_configure(
		self,
		event,
	):
		self.sidebar_canvas.configure(
			scrollregion=self.sidebar_canvas.bbox(
				"all"
			)
		)

	def _on_sidebar_canvas_configure(
		self,
		event,
	):
		self.sidebar_canvas.itemconfigure(
			self.sidebar_window,
			width=event.width,
		)

	def _on_sidebar_mousewheel(
		self,
		event,
	):
		widget = self.root.winfo_containing(
			event.x_root,
			event.y_root,
		)

		current = widget

		while current is not None:
			if current == self.sidebar_canvas:
				break

			try:
				current = current.master
			except Exception:
				current = None

		if current != self.sidebar_canvas:
			return

		delta = int(
			-event.delta / 120
		)

		if delta == 0:
			delta = -1 if event.delta > 0 else 1

		self.sidebar_canvas.yview_scroll(
			delta,
			"units",
		)

	def _bind_events(self):
		self.nickname_var.trace_add(
			"write",
			self._on_nickname_changed,
		)

		self.nickname_entry.bind(
			"<FocusIn>",
			self._on_entry_focus,
		)

		self.sample_canvas.bind(
			"<Configure>",
			lambda event: self._redraw_sample(),
		)

		self.dictionary_canvas.bind(
			"<Configure>",
			lambda event: self._draw_dictionary_progress(),
		)

		self.sample_canvas.bind(
			"<ButtonPress-1>",
			self._on_crop_start,
		)

		self.sample_canvas.bind(
			"<B1-Motion>",
			self._on_crop_drag,
		)

		self.sample_canvas.bind(
			"<ButtonRelease-1>",
			self._on_crop_end,
		)

		self.sample_canvas.bind(
			"<Button-3>",
			lambda event: self._reset_crop(),
		)

		self.root.bind(
			"<Return>",
			lambda event: self._accept_sample(),
		)

		self.root.bind(
			"<Control-s>",
			lambda event: self._skip_sample(),
		)

		self.root.bind(
			"<Control-Left>",
			lambda event: self._previous_sample(),
		)

		self.root.bind(
			"<Control-Right>",
			lambda event: self._next_sample(),
		)

		self.root.bind(
			"<Escape>",
			lambda event: self._quit(),
		)

		self.root.protocol(
			"WM_DELETE_WINDOW",
			self._quit,
		)

	def _load_current_sample(self):
		if not self.sample_paths:
			return

		self.index = max(
			0,
			min(
				self.index,
				len(self.sample_paths) - 1,
			),
		)

		self.sample_path = self.sample_paths[
			self.index
		]

		self.sample_image = cv2.imread(
			str(
				self.sample_path
			)
		)

		if self.sample_image is None:
			self.status_var.set(
				f"Не удалось открыть: {self.sample_path}"
			)
			return

		height, width = self.sample_image.shape[:2]
		self.crop_rect = (
			0,
			0,
			width,
			height,
		)

		record = self._record_for_current()

		if record:
			nickname = str(
				record.get(
					"nickname",
					"",
				)
			).lower()

			self._set_real_nickname(
				nickname
			)

			crop = record.get(
				"crop"
			)

			if (
				isinstance(
					crop,
					list,
				)
				and len(crop) == 4
			):
				self.crop_rect = tuple(
					int(value)
					for value in crop
				)
		else:
			self._set_real_nickname(
				""
			)

		self.segmented = None
		self.segment_photos = []
		self.file_var.set(
			str(
				self.sample_path.relative_to(
					self.project_root
				)
			)
		)

		self.progress_var.set(
			f"{self.index + 1} / "
			f"{len(self.sample_paths)}"
		)

		self.status_var.set(
			"Проверь crop, затем подтверди или введи правильный ник."
		)

		self.check_var.set(
			"Проверка шаблонами: —"
		)

		self.guess_value = ""
		self.guess_var.set(
			"Похоже на: определяю..."
		)

		self._update_navigation_buttons()
		self.root.after(
			20,
			self._redraw_sample,
		)

		self._schedule_guess()
		self._schedule_preview()
		self.nickname_entry.focus_set()

	def _schedule_guess(self):
		if self.guess_job is not None:
			try:
				self.root.after_cancel(
					self.guess_job
				)
			except tk.TclError:
				pass

		self.guess_job = self.root.after(
			80,
			self._compute_guess,
		)

	def _compute_guess(self):
		self.guess_job = None
		crop = self._get_crop_image()

		if crop is None:
			self.guess_value = ""
			self.guess_var.set(
				"Похоже на: —"
			)
			return

		try:
			guess = (
				read_player_name(
					crop
				)
				.strip()
				.lower()
			)
		except Exception:
			guess = ""

		guess = "".join(
			character
			for character in guess
			if character
			in LOWER_NAME_CHARS
		)

		self.guess_value = guess

		if guess:
			self.guess_var.set(
				f"Похоже на: {guess}"
			)

			if not self._real_nickname():
				self._show_placeholder(
					guess
				)
		else:
			self.guess_var.set(
				"Похоже на: —"
			)

	def _show_placeholder(
		self,
		value,
	):
		if self._real_nickname():
			return

		self.placeholder_active = True
		self.placeholder_value = value

		self.nickname_entry.config(
			fg="#777777"
		)

		self.nickname_var.set(
			value
		)

	def _on_entry_focus(
		self,
		event,
	):
		if self.placeholder_active:
			self.placeholder_active = False
			self.placeholder_value = ""

			self.nickname_var.set(
				""
			)

			self.nickname_entry.config(
				fg="#000000"
			)

	def _insert_guess(self):
		if not self.guess_value:
			return

		self._set_real_nickname(
			self.guess_value
		)

		self.nickname_entry.focus_set()
		self.nickname_entry.icursor(
			tk.END
		)

	def _set_real_nickname(
		self,
		value,
	):
		self.placeholder_active = False
		self.placeholder_value = ""

		self.nickname_entry.config(
			fg="#000000"
		)

		self.nickname_var.set(
			value.lower()
		)

	def _real_nickname(self):
		if self.placeholder_active:
			return ""

		return (
			self.nickname_var.get()
			.strip()
			.lower()
		)

	def _on_nickname_changed(
		self,
		*args,
	):
		if self.placeholder_active:
			return

		value = (
			self.nickname_var.get()
			.lower()
		)

		filtered = "".join(
			character
			for character in value
			if character in LOWER_NAME_CHARS
		)

		if filtered != self.nickname_var.get():
			self.nickname_var.set(
				filtered
			)
			return

		self._schedule_preview()

	def _schedule_preview(self):
		if self.preview_job is not None:
			try:
				self.root.after_cancel(
					self.preview_job
				)
			except tk.TclError:
				pass

		self.preview_job = self.root.after(
			DEBOUNCE_MS,
			self._recompute_preview,
		)

	def _recompute_preview(self):
		self.preview_job = None
		self.segmented = None
		self.segment_canvas.delete(
			"all"
		)

		nickname = self._real_nickname()

		if not nickname:
			self.check_var.set(
				"Проверка шаблонами: сначала подтверди ник."
			)

			self._update_accept_button()
			return

		crop = self._get_crop_image()

		if crop is None:
			self.status_var.set(
				"Crop пуст."
			)

			self._update_accept_button()
			return

		segmented = segment_known_name(
			self.project_root,
			crop,
			nickname,
		)

		if segmented is None:
			self.status_var.set(
				"Сегментация не сошлась. Поправь crop."
			)

			self.check_var.set(
				"Проверка шаблонами: сегментация не удалась."
			)

			self._update_accept_button()
			return

		self.segmented = segmented

		matches = self._draw_segments(
			segmented,
			nickname,
		)

		total = len(
			nickname
		)

		if total:
			percent = int(
				round(
					matches
					/ total
					* 100
				)
			)
		else:
			percent = 0

		self.check_var.set(
			f"Проверка шаблонами: {matches}/{total} совпали ({percent}%)."
		)

		self.status_var.set(
			"Зелёный = шаблон согласен с truth. "
			"Красный = модель ошиблась или сегмент подозрительный."
		)

		self._update_accept_button()

	def _draw_segments(
		self,
		segmented,
		nickname,
	):
		self.segment_canvas.delete(
			"all"
		)

		self.segment_photos = []
		x = 10
		y = 10
		matches = 0

		for index, segment in enumerate(
			segmented.segments
		):
			truth = nickname[
				index
			]

			predicted, score = (
				self.predictor.predict(
					segment
				)
			)

			if predicted == truth:
				matches += 1
				outline = "#25c95a"
				pred_color = "#25c95a"
			else:
				outline = "#e54848"
				pred_color = "#e54848"

			image = Image.fromarray(
				segment
			).convert(
				"L"
			)

			image = image.resize(
				(
					SEGMENT_BOX_WIDTH,
					SEGMENT_BOX_HEIGHT - 42,
				),
				resample=Image.Resampling.NEAREST,
			)

			photo = ImageTk.PhotoImage(
				image
			)

			self.segment_photos.append(
				photo
			)

			self.segment_canvas.create_rectangle(
				x,
				y,
				x + SEGMENT_BOX_WIDTH,
				y + SEGMENT_BOX_HEIGHT,
				outline=outline,
				width=2,
				fill="#080808",
			)

			self.segment_canvas.create_image(
				x,
				y,
				image=photo,
				anchor="nw",
			)

			self.segment_canvas.create_text(
				x + 4,
				y + SEGMENT_BOX_HEIGHT - 30,
				text=f"truth: {truth}",
				fill="#dddddd",
				font=(
					"Consolas",
					9,
				),
				anchor="w",
			)

			pred_text = (
				f"pred: {predicted or '?'} "
				f"{int(score * 100)}%"
			)

			self.segment_canvas.create_text(
				x + 4,
				y + SEGMENT_BOX_HEIGHT - 13,
				text=pred_text,
				fill=pred_color,
				font=(
					"Consolas",
					8,
				),
				anchor="w",
			)

			x += (
				SEGMENT_BOX_WIDTH
				+ SEGMENT_GAP
			)

		self.segment_canvas.configure(
			scrollregion=(
				0,
				0,
				max(
					x + 10,
					self.segment_canvas.winfo_width(),
				),
				SEGMENT_BOX_HEIGHT + 20,
			)
		)

		return matches

	def _refresh_dictionary_progress(self):
		root = (
			self.project_root
			/ "assets"
			/ "players"
			/ "templates"
			/ "chars"
		)

		counts = {}

		for character in LOWER_NAME_CHARS:
			folder = root / character

			if folder.exists():
				count = len(
					list(
						folder.glob(
							"*.png"
						)
					)
				)
			else:
				count = 0

			counts[
				character
			] = count

		self.dictionary_counts = counts

		ready = sum(
			1
			for count in counts.values()
			if count >= CHAR_READY_TARGET
		)

		good = sum(
			1
			for count in counts.values()
			if count >= CHAR_GOOD_TARGET
		)

		minimum = sum(
			1
			for count in counts.values()
			if count >= CHAR_MINIMUM_TARGET
		)

		total = len(
			LOWER_NAME_CHARS
		)

		total_samples = sum(
			counts.values()
		)

		weak = [
			character
			for character, count in counts.items()
			if count < CHAR_MINIMUM_TARGET
		]

		weak_preview = " ".join(
			weak[:14]
		)

		if len(weak) > 14:
			weak_preview += " …"

		self.dictionary_summary_var.set(
			f"Готово: {ready}/{total}   "
			f"Хорошо (≥10): {good}/{total}\n"
			f"Минимум (≥5): {minimum}/{total}   "
			f"Всего samples: {total_samples}\n"
			f"Слабые: {weak_preview or 'нет'}"
		)

		self._draw_dictionary_progress()

	def _draw_dictionary_progress(self):
		if not hasattr(
			self,
			"dictionary_canvas",
		):
			return

		canvas = self.dictionary_canvas
		canvas.delete(
			"all"
		)

		width = max(
			330,
			canvas.winfo_width(),
		)

		columns = 4
		cell_width = (
			width - 12
		) // columns

		cell_height = 38

		for index, character in enumerate(
			LOWER_NAME_CHARS
		):
			row = index // columns
			column = index % columns

			x = 6 + column * cell_width
			y = 5 + row * cell_height

			count = self.dictionary_counts.get(
				character,
				0,
			)

			progress = min(
				1.0,
				count / float(
					CHAR_READY_TARGET
				),
			)

			if count >= CHAR_READY_TARGET:
				color = "#34c759"
				state = "✓"
			elif count >= CHAR_GOOD_TARGET:
				color = "#9acd32"
				state = "○"
			elif count >= CHAR_MINIMUM_TARGET:
				color = "#f0b429"
				state = "·"
			else:
				color = "#d9534f"
				state = "!"

			canvas.create_rectangle(
				x,
				y,
				x + cell_width - 6,
				y + 31,
				outline="#444444",
				fill="#202020",
			)

			bar_width = int(
				(cell_width - 8)
				* progress
			)

			if bar_width > 0:
				canvas.create_rectangle(
					x + 1,
					y + 24,
					x + 1 + bar_width,
					y + 30,
					outline="",
					fill=color,
				)

			canvas.create_text(
				x + 6,
				y + 10,
				text=character,
				fill="#f2f2f2",
				font=(
					"Consolas",
					11,
					"bold",
				),
				anchor="w",
			)

			canvas.create_text(
				x + cell_width - 12,
				y + 10,
				text=f"{state}{count}",
				fill=color,
				font=(
					"Consolas",
					9,
					"bold",
				),
				anchor="e",
			)

			canvas.create_text(
				x + 6,
				y + 20,
				text=f"{int(progress * 100)}%",
				fill="#aaaaaa",
				font=(
					"Segoe UI",
					7,
				),
				anchor="w",
			)

		rows = (
			len(LOWER_NAME_CHARS)
			+ columns - 1
		) // columns

		canvas.configure(
			height=rows * cell_height + 8
		)

	def _redraw_sample(self):
		if self.sample_image is None:
			return

		canvas_width = max(
			1,
			self.sample_canvas.winfo_width(),
		)

		canvas_height = max(
			1,
			self.sample_canvas.winfo_height(),
		)

		image_height, image_width = (
			self.sample_image.shape[:2]
		)

		max_width = min(
			canvas_width - 20,
			SAMPLE_MAX_WIDTH,
		)

		max_height = min(
			canvas_height - 20,
			SAMPLE_MAX_HEIGHT,
		)

		scale = min(
			max_width / max(
				image_width,
				1,
			),
			max_height / max(
				image_height,
				1,
			),
		)

		scale = max(
			1.0,
			scale,
		)

		display_width = max(
			1,
			int(
				round(
					image_width * scale
				)
			),
		)

		display_height = max(
			1,
			int(
				round(
					image_height * scale
				)
			),
		)

		offset_x = max(
			10,
			(
				canvas_width
				- display_width
			) // 2,
		)

		offset_y = max(
			10,
			(
				canvas_height
				- display_height
			) // 2,
		)

		self.sample_transform = ImageTransform(
			scale=scale,
			offset_x=offset_x,
			offset_y=offset_y,
			display_width=display_width,
			display_height=display_height,
		)

		rgb = cv2.cvtColor(
			self.sample_image,
			cv2.COLOR_BGR2RGB,
		)

		image = Image.fromarray(
			rgb
		).resize(
			(
				display_width,
				display_height,
			),
			resample=Image.Resampling.NEAREST,
		)

		self.sample_photo = (
			ImageTk.PhotoImage(
				image
			)
		)

		self.sample_canvas.delete(
			"all"
		)

		self.sample_canvas.create_image(
			offset_x,
			offset_y,
			image=self.sample_photo,
			anchor="nw",
		)

		self._draw_crop_rect()

	def _draw_crop_rect(self):
		if self.crop_rect is None:
			return

		x1, y1, x2, y2 = (
			self.crop_rect
		)

		sx1, sy1 = self._image_to_canvas(
			x1,
			y1,
		)

		sx2, sy2 = self._image_to_canvas(
			x2,
			y2,
		)

		self.sample_canvas.create_rectangle(
			sx1,
			sy1,
			sx2,
			sy2,
			outline="#38E875",
			width=2,
		)

		self.crop_var.set(
			f"Crop x={x1}:{x2}, y={y1}:{y2}. "
			f"ЛКМ drag — изменить, ПКМ — сбросить."
		)

	def _on_crop_start(
		self,
		event,
	):
		point = self._canvas_to_image(
			event.x,
			event.y,
		)

		if point is None:
			return

		self.drag_start = point

	def _on_crop_drag(
		self,
		event,
	):
		if self.drag_start is None:
			return

		current = self._canvas_to_image(
			event.x,
			event.y,
			clamp=True,
		)

		if current is None:
			return

		self._redraw_sample()

		x1, y1 = self._image_to_canvas(
			*self.drag_start
		)

		x2, y2 = self._image_to_canvas(
			*current
		)

		self.sample_canvas.create_rectangle(
			x1,
			y1,
			x2,
			y2,
			outline="#FFD54F",
			width=2,
			dash=(5, 3),
		)

	def _on_crop_end(
		self,
		event,
	):
		if self.drag_start is None:
			return

		current = self._canvas_to_image(
			event.x,
			event.y,
			clamp=True,
		)

		start = self.drag_start
		self.drag_start = None

		if current is None:
			return

		x1 = min(
			start[0],
			current[0],
		)

		y1 = min(
			start[1],
			current[1],
		)

		x2 = max(
			start[0],
			current[0],
		)

		y2 = max(
			start[1],
			current[1],
		)

		if (
			x2 - x1 < 4
			or y2 - y1 < 4
		):
			return

		self.crop_rect = (
			x1,
			y1,
			x2,
			y2,
		)

		self._redraw_sample()
		self._schedule_guess()
		self._schedule_preview()

	def _canvas_to_image(
		self,
		x,
		y,
		clamp=False,
	):
		transform = self.sample_transform
		local_x = (
			x - transform.offset_x
		)

		local_y = (
			y - transform.offset_y
		)

		if not clamp:
			if (
				local_x < 0
				or local_y < 0
				or local_x >= transform.display_width
				or local_y >= transform.display_height
			):
				return None

		local_x = max(
			0,
			min(
				local_x,
				transform.display_width - 1,
			),
		)

		local_y = max(
			0,
			min(
				local_y,
				transform.display_height - 1,
			),
		)

		image_x = int(
			round(
				local_x / transform.scale
			)
		)

		image_y = int(
			round(
				local_y / transform.scale
			)
		)

		image_x = max(
			0,
			min(
				image_x,
				self.sample_image.shape[1] - 1,
			),
		)

		image_y = max(
			0,
			min(
				image_y,
				self.sample_image.shape[0] - 1,
			),
		)

		return (
			image_x,
			image_y,
		)

	def _image_to_canvas(
		self,
		x,
		y,
	):
		transform = self.sample_transform

		return (
			transform.offset_x
			+ int(
				round(
					x * transform.scale
				)
			),
			transform.offset_y
			+ int(
				round(
					y * transform.scale
				)
			),
		)

	def _get_crop_image(self):
		if (
			self.sample_image is None
			or self.crop_rect is None
		):
			return None

		x1, y1, x2, y2 = (
			self.crop_rect
		)

		x1 = max(
			0,
			min(
				x1,
				self.sample_image.shape[1] - 1,
			),
		)

		y1 = max(
			0,
			min(
				y1,
				self.sample_image.shape[0] - 1,
			),
		)

		x2 = max(
			x1 + 1,
			min(
				x2,
				self.sample_image.shape[1],
			),
		)

		y2 = max(
			y1 + 1,
			min(
				y2,
				self.sample_image.shape[0],
			),
		)

		return self.sample_image[
			y1:y2,
			x1:x2,
		].copy()

	def _auto_crop(self):
		if self.sample_image is None:
			return

		rect = find_auto_crop_rect(
			self.sample_image
		)

		if rect is None:
			self.status_var.set(
				"Auto crop не нашёл текст."
			)
			return

		self.crop_rect = rect
		self._redraw_sample()
		self._schedule_guess()
		self._schedule_preview()

	def _reset_crop(self):
		if self.sample_image is None:
			return

		height, width = (
			self.sample_image.shape[:2]
		)

		self.crop_rect = (
			0,
			0,
			width,
			height,
		)

		self._redraw_sample()
		self._schedule_guess()
		self._schedule_preview()

	def _clear_nickname(self):
		self._set_real_nickname(
			""
		)

		if self.guess_value:
			self._show_placeholder(
				self.guess_value
			)

	def _accept_sample(self):
		nickname = self._real_nickname()

		if not nickname:
			self.status_var.set(
				"Placeholder — это подсказка. "
				"Сначала подтверди ник кнопкой «Вставить» или введи вручную."
			)
			return

		if self.segmented is None:
			self._recompute_preview()

		if self.segmented is None:
			self.status_var.set(
				"Нельзя принять: сегментация невалидна."
			)
			return

		crop = self._get_crop_image()

		save_name_template(
			self.project_root,
			nickname,
			crop,
		)

		accept_segmented_sample(
			self.project_root,
			nickname,
			self.segmented,
		)

		self.predictor.reload()
		self._refresh_dictionary_progress()

		self._save_record(
			status="accepted",
			nickname=nickname,
		)

		self._move_to_index(
			self.index + 1
		)

	def _skip_sample(self):
		self._save_record(
			status="skipped",
			nickname=self._real_nickname(),
		)

		self._move_to_index(
			self.index + 1
		)

	def _previous_sample(self):
		self._move_to_index(
			self.index - 1
		)

	def _next_sample(self):
		self._move_to_index(
			self.index + 1
		)

	def _move_to_index(
		self,
		index,
	):
		self.index = max(
			0,
			min(
				index,
				len(self.sample_paths) - 1,
			),
		)

		self._load_current_sample()

	def _update_navigation_buttons(self):
		if self.index <= 0:
			self.previous_button.state(
				["disabled"]
			)
		else:
			self.previous_button.state(
				["!disabled"]
			)

		if (
			self.index
			>= len(self.sample_paths) - 1
		):
			self.next_button.state(
				["disabled"]
			)
		else:
			self.next_button.state(
				["!disabled"]
			)

		self._update_accept_button()

	def _update_accept_button(self):
		if (
			self.segmented is not None
			and bool(
				self._real_nickname()
			)
		):
			self.accept_button.state(
				["!disabled"]
			)
		else:
			self.accept_button.state(
				["disabled"]
			)

	def _record_for_current(self):
		if self.sample_path is None:
			return None

		return self.state.get(
			"samples",
			{},
		).get(
			self._sample_key(
				self.sample_path
			)
		)

	def _sample_key(
		self,
		path,
	):
		return str(
			path.relative_to(
				self.project_root
			)
		).replace(
			"\\",
			"/",
		)

	def _save_record(
		self,
		status,
		nickname,
	):
		if self.sample_path is None:
			return

		samples = self.state.setdefault(
			"samples",
			{},
		)

		samples[
			self._sample_key(
				self.sample_path
			)
		] = {
			"status": status,
			"nickname": nickname,
			"crop": list(
				self.crop_rect
			),
		}

		self.state[
			"last_index"
		] = self.index

		self._save_state()

	def _load_state(self):
		if not self.state_path.exists():
			return {
				"samples": {},
				"last_index": 0,
			}

		try:
			return json.loads(
				self.state_path.read_text(
					encoding="utf-8"
				)
			)
		except Exception:
			return {
				"samples": {},
				"last_index": 0,
			}

	def _save_state(self):
		self.state_path.parent.mkdir(
			parents=True,
			exist_ok=True,
		)

		self.state_path.write_text(
			json.dumps(
				self.state,
				ensure_ascii=False,
				indent=2,
			),
			encoding="utf-8",
		)

	def _resolve_start_index(self):
		samples = self.state.get(
			"samples",
			{},
		)

		for index, path in enumerate(
			self.sample_paths
		):
			record = samples.get(
				self._sample_key(
					path
				)
			)

			if not record:
				return index

			if record.get(
				"status"
			) not in {
				"accepted",
				"skipped",
			}:
				return index

		return max(
			0,
			min(
				int(
					self.state.get(
						"last_index",
						0,
					)
				),
				len(self.sample_paths) - 1,
			),
		)

	def _quit(self):
		self.state[
			"last_index"
		] = self.index

		self._save_state()
		self.root.destroy()


def find_auto_crop_rect(
	image,
):
	gray = cv2.cvtColor(
		image,
		cv2.COLOR_BGR2GRAY,
	)

	gray = cv2.GaussianBlur(
		gray,
		(3, 3),
		0,
	)

	_, binary = cv2.threshold(
		gray,
		0,
		255,
		cv2.THRESH_BINARY + cv2.THRESH_OTSU,
	)

	white_ratio = (
		cv2.countNonZero(
			binary
		)
		/ float(
			binary.shape[0]
			* binary.shape[1]
		)
	)

	if white_ratio > 0.55:
		binary = cv2.bitwise_not(
			binary
		)

	points = cv2.findNonZero(
		binary
	)

	if points is None:
		return None

	x, y, width, height = (
		cv2.boundingRect(
			points
		)
	)

	pad_x = max(
		6,
		int(
			round(
				width * 0.06
			)
		),
	)

	# Снизу нужен заметный запас: именно там живёт '_'.
	pad_top = max(
		3,
		int(
			round(
				height * 0.10
			)
		),
	)

	pad_bottom = max(
		7,
		int(
			round(
				height * 0.28
			)
		),
	)

	left = max(
		0,
		x - pad_x,
	)

	top = max(
		0,
		y - pad_top,
	)

	right = min(
		image.shape[1],
		x + width + pad_x,
	)

	bottom = min(
		image.shape[0],
		y + height + pad_bottom,
	)

	return (
		left,
		top,
		right,
		bottom,
	)


def collect_name_samples(
	project_root,
):
	return sorted(
		(
			project_root
			/ "captures"
		).glob(
			"table_*/names/*.png"
		)
	)


def main():
	project_root = find_project_root()

	sample_paths = collect_name_samples(
		project_root
	)

	if not sample_paths:
		print(
			"No captured name samples found."
		)
		return

	root = tk.Tk()

	NameLabelerApp(
		root,
		project_root,
		sample_paths,
	)

	root.mainloop()


if __name__ == "__main__":
	main()
