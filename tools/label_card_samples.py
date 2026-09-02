from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import tkinter as tk
from tkinter import ttk

import cv2
import numpy as np
from PIL import Image, ImageTk

from poker.vision.project_paths import find_project_root
from poker.vision.recognition.card_features import (
	rank_feature,
	similarity,
	suit_feature,
)


WINDOW_TITLE = "Neuro Poker — Разметка карт"
WINDOW_WIDTH = 1420
WINDOW_HEIGHT = 900

VALID_RANKS = "AKQJT98765432"
VALID_SUITS = "shdc"

RANK_READY_TARGET = 12
RANK_GOOD_TARGET = 8
RANK_MINIMUM_TARGET = 4

SUIT_READY_TARGET = 30
SUIT_GOOD_TARGET = 18
SUIT_MINIMUM_TARGET = 8


@dataclass
class Guess:
	rank: str = ""
	rank_score: float = 0.0
	suit: str = ""
	suit_score: float = 0.0

	@property
	def label(self):
		if not self.rank and not self.suit:
			return ""

		return (
			f"{self.rank or '?'}"
			f"{self.suit or '?'}"
		)

	@property
	def confidence(self):
		scores = []

		if self.rank:
			scores.append(
				self.rank_score
			)

		if self.suit:
			scores.append(
				self.suit_score
			)

		if not scores:
			return 0.0

		return sum(scores) / len(scores)


class TemplateGuesser:
	def __init__(
		self,
		project_root: Path,
	):
		self.project_root = project_root
		self.template_root = (
			project_root
			/ "assets"
			/ "cards"
			/ "templates"
		)

		self.rank_templates = {}
		self.suit_templates = {}

		self.reload()

	def reload(self):
		self.rank_templates = self._load_templates(
			self.template_root
			/ "ranks"
		)

		self.suit_templates = self._load_templates(
			self.template_root
			/ "suits"
		)

	def guess(
		self,
		card_image,
	):
		rank, rank_score = self._match(
			rank_feature(
				card_image
			),
			self.rank_templates,
		)

		suit, suit_score = self._match(
			suit_feature(
				card_image
			),
			self.suit_templates,
		)

		return Guess(
			rank=rank,
			rank_score=rank_score,
			suit=suit,
			suit_score=suit_score,
		)

	def _load_templates(
		self,
		root,
	):
		result = {}

		if not root.exists():
			return result

		for folder in root.iterdir():
			if not folder.is_dir():
				continue

			images = []

			for path in folder.glob(
				"*.png"
			):
				image = cv2.imread(
					str(path),
					cv2.IMREAD_GRAYSCALE,
				)

				if image is None:
					continue

				images.append(
					image
				)

			if images:
				result[
					folder.name
				] = images

		return result

	def _match(
		self,
		feature,
		templates,
	):
		if feature is None:
			return (
				"",
				0.0,
			)

		best_label = ""
		best_score = 0.0

		for label, images in (
			templates.items()
		):
			for image in images:
				score = similarity(
					feature,
					image,
				)

				if score > best_score:
					best_label = label
					best_score = score

		return (
			best_label,
			best_score,
		)


class CardLabelerApp:
	def __init__(
		self,
		root: tk.Tk,
		project_root: Path,
		samples: list[Path],
	):
		self.root = root
		self.project_root = project_root
		self.samples = samples

		self.template_root = (
			project_root
			/ "assets"
			/ "cards"
			/ "templates"
		)

		self.state_path = (
			project_root
			/ "captures"
			/ "card_labeler_state.json"
		)

		self.state = self._load_state()
		self.index = self._resolve_start_index()

		self.guesser = TemplateGuesser(
			project_root
		)

		self.sample_path = None
		self.card_image = None
		self.card_photo = None
		self.rank_photo = None
		self.suit_photo = None

		self.guess = Guess()
		self.placeholder_active = False

		self.label_var = tk.StringVar()
		self.file_var = tk.StringVar()
		self.progress_var = tk.StringVar()
		self.guess_var = tk.StringVar(
			value="Похоже на: —"
		)
		self.guess_details_var = tk.StringVar(
			value="rank: —   suit: —"
		)
		self.status_var = tk.StringVar()
		self.rank_summary_var = tk.StringVar()
		self.suit_summary_var = tk.StringVar()

		self.rank_counts = {}
		self.suit_counts = {}

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
			1120,
			720,
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
			text="Разметка карт",
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

		card_frame = ttk.LabelFrame(
			left,
			text="1. Карта",
			padding=8,
		)

		card_frame.grid(
			row=1,
			column=0,
			sticky="nsew",
		)

		card_frame.columnconfigure(
			0,
			weight=1,
		)

		card_frame.rowconfigure(
			0,
			weight=1,
		)

		self.card_canvas = tk.Canvas(
			card_frame,
			background="#111111",
			highlightthickness=0,
		)

		self.card_canvas.grid(
			row=0,
			column=0,
			sticky="nsew",
		)

		feature_frame = ttk.LabelFrame(
			left,
			text="2. Что именно сохраняется в шаблоны",
			padding=8,
		)

		feature_frame.grid(
			row=2,
			column=0,
			sticky="ew",
			pady=(8, 0),
		)

		feature_frame.columnconfigure(
			0,
			weight=1,
		)

		feature_frame.columnconfigure(
			1,
			weight=1,
		)

		self.rank_feature_label = ttk.Label(
			feature_frame,
			text="rank feature",
			anchor="center",
		)

		self.rank_feature_label.grid(
			row=0,
			column=0,
			sticky="nsew",
			padx=(0, 4),
		)

		self.suit_feature_label = ttk.Label(
			feature_frame,
			text="suit feature",
			anchor="center",
		)

		self.suit_feature_label.grid(
			row=0,
			column=1,
			sticky="nsew",
			padx=(4, 0),
		)

		sidebar_outer = ttk.Frame(
			main,
			width=450,
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

		scrollbar = ttk.Scrollbar(
			sidebar_outer,
			orient=tk.VERTICAL,
			command=self.sidebar_canvas.yview,
		)

		scrollbar.grid(
			row=0,
			column=1,
			sticky="ns",
		)

		self.sidebar_canvas.configure(
			yscrollcommand=scrollbar.set
		)

		sidebar = ttk.Frame(
			self.sidebar_canvas,
			padding=(4, 0, 8, 0),
		)

		self.sidebar_window = (
			self.sidebar_canvas.create_window(
				(0, 0),
				window=sidebar,
				anchor="nw",
			)
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

		ttk.Label(
			sidebar,
			text="3. Правильная карта",
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

		self.label_entry = tk.Entry(
			sidebar,
			textvariable=self.label_var,
			font=(
				"Consolas",
				22,
				"bold",
			),
			relief=tk.SOLID,
			borderwidth=1,
			justify=tk.CENTER,
		)

		self.label_entry.grid(
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
			pady=(6, 2),
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
				10,
			),
			foreground="#666666",
		).grid(
			row=0,
			column=0,
			sticky="w",
		)

		ttk.Button(
			guess_row,
			text="Вставить",
			command=self._insert_guess,
		).grid(
			row=0,
			column=1,
			sticky="e",
		)

		ttk.Label(
			sidebar,
			textvariable=self.guess_details_var,
			font=(
				"Consolas",
				9,
			),
		).grid(
			row=3,
			column=0,
			sticky="w",
			pady=(0, 12),
		)

		self.accept_button = ttk.Button(
			sidebar,
			text="✓ Принять карту",
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
			pady=(0, 16),
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

		ttk.Label(
			sidebar,
			text=(
				"Формат: Ah, Ks, Td, 7c\n"
				"Ранг: A K Q J T 9..2\n"
				"Масть: s h d c\n\n"
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
			row=7,
			column=0,
			sticky="w",
			pady=(0, 14),
		)

		ttk.Separator(
			sidebar,
			orient=tk.HORIZONTAL,
		).grid(
			row=8,
			column=0,
			sticky="ew",
			pady=(0, 10),
		)

		ttk.Label(
			sidebar,
			text="Прогресс рангов",
			font=(
				"Segoe UI",
				11,
				"bold",
			),
		).grid(
			row=9,
			column=0,
			sticky="w",
		)

		ttk.Label(
			sidebar,
			textvariable=self.rank_summary_var,
			font=(
				"Segoe UI",
				9,
			),
			justify=tk.LEFT,
		).grid(
			row=10,
			column=0,
			sticky="w",
			pady=(2, 5),
		)

		self.rank_canvas = tk.Canvas(
			sidebar,
			height=245,
			background="#151515",
			highlightthickness=0,
		)

		self.rank_canvas.grid(
			row=11,
			column=0,
			sticky="ew",
		)

		ttk.Separator(
			sidebar,
			orient=tk.HORIZONTAL,
		).grid(
			row=12,
			column=0,
			sticky="ew",
			pady=(14, 10),
		)

		ttk.Label(
			sidebar,
			text="Прогресс мастей",
			font=(
				"Segoe UI",
				11,
				"bold",
			),
		).grid(
			row=13,
			column=0,
			sticky="w",
		)

		ttk.Label(
			sidebar,
			textvariable=self.suit_summary_var,
			font=(
				"Segoe UI",
				9,
			),
			justify=tk.LEFT,
		).grid(
			row=14,
			column=0,
			sticky="w",
			pady=(2, 5),
		)

		self.suit_canvas = tk.Canvas(
			sidebar,
			height=120,
			background="#151515",
			highlightthickness=0,
		)

		self.suit_canvas.grid(
			row=15,
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

	def _bind_events(self):
		self.label_var.trace_add(
			"write",
			self._on_label_changed,
		)

		self.label_entry.bind(
			"<FocusIn>",
			self._on_entry_focus,
		)

		self.card_canvas.bind(
			"<Configure>",
			lambda event: self._redraw_card(),
		)

		self.rank_canvas.bind(
			"<Configure>",
			lambda event: self._draw_rank_progress(),
		)

		self.suit_canvas.bind(
			"<Configure>",
			lambda event: self._draw_suit_progress(),
		)

		self.sidebar_canvas.bind_all(
			"<MouseWheel>",
			self._on_mousewheel,
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
		if not self.samples:
			return

		self.index = max(
			0,
			min(
				self.index,
				len(self.samples) - 1,
			),
		)

		self.sample_path = self.samples[
			self.index
		]

		self.card_image = cv2.imread(
			str(
				self.sample_path
			)
		)

		if self.card_image is None:
			self.status_var.set(
				f"Не удалось открыть {self.sample_path}"
			)
			return

		record = self._record_for_current()

		if record:
			label = str(
				record.get(
					"label",
					"",
				)
			)

			self._set_real_label(
				label
			)
		else:
			self._set_real_label(
				""
			)

		self.file_var.set(
			str(
				self.sample_path.relative_to(
					self.project_root
				)
			)
		)

		self.progress_var.set(
			f"{self.index + 1} / {len(self.samples)}"
		)

		self.guess = self.guesser.guess(
			self.card_image
		)

		self._show_guess()
		self._draw_features()
		self._update_navigation()
		self.root.after(
			10,
			self._redraw_card,
		)

		self.label_entry.focus_set()

	def _show_guess(self):
		if self.guess.label:
			self.guess_var.set(
				f"Похоже на: {self.guess.label}"
			)

			self.guess_details_var.set(
				f"rank {self.guess.rank or '?'} "
				f"{self.guess.rank_score * 100:.0f}%   "
				f"suit {self.guess.suit or '?'} "
				f"{self.guess.suit_score * 100:.0f}%"
			)

			if not self._real_label():
				self._show_placeholder(
					self.guess.label
				)
		else:
			self.guess_var.set(
				"Похоже на: —"
			)

			self.guess_details_var.set(
				"rank: шаблонов нет   suit: шаблонов нет"
			)

	def _show_placeholder(
		self,
		value,
	):
		self.placeholder_active = True

		self.label_entry.config(
			fg="#777777"
		)

		self.label_var.set(
			value
		)

	def _on_entry_focus(
		self,
		event,
	):
		if not self.placeholder_active:
			return

		self.placeholder_active = False
		self.label_entry.config(
			fg="#000000"
		)

		self.label_var.set(
			""
		)

	def _insert_guess(self):
		if not self.guess.label:
			return

		if "?" in self.guess.label:
			return

		self._set_real_label(
			self.guess.label
		)

		self.label_entry.focus_set()
		self.label_entry.icursor(
			tk.END
		)

	def _set_real_label(
		self,
		value,
	):
		self.placeholder_active = False
		self.label_entry.config(
			fg="#000000"
		)

		self.label_var.set(
			self._normalize_label_text(
				value
			)
		)

	def _real_label(self):
		if self.placeholder_active:
			return ""

		return self._normalize_label_text(
			self.label_var.get()
		)

	def _on_label_changed(
		self,
		*args,
	):
		if self.placeholder_active:
			return

		raw = self.label_var.get()
		filtered = self._normalize_label_text(
			raw
		)

		if filtered != raw:
			self.label_var.set(
				filtered
			)
			return

		self._update_accept_button()

	def _normalize_label_text(
		self,
		value,
	):
		value = str(
			value
		).strip()

		if not value:
			return ""

		result = ""

		first = value[
			0
		].upper()

		if first in VALID_RANKS:
			result += first

		if len(value) >= 2:
			second = value[
				1
			].lower()

			if second in VALID_SUITS:
				result += second

		return result[:2]

	def _is_valid_label(
		self,
		label,
	):
		return (
			len(label) == 2
			and label[0] in VALID_RANKS
			and label[1] in VALID_SUITS
		)

	def _accept_sample(self):
		label = self._real_label()

		if not self._is_valid_label(
			label
		):
			self.status_var.set(
				"Введи карту в формате Ah / Ks / Td / 7c."
			)
			return

		rank = label[0]
		suit = label[1]

		rank_image = rank_feature(
			self.card_image
		)

		suit_image = suit_feature(
			self.card_image
		)

		if rank_image is None:
			self.status_var.set(
				"Не удалось выделить rank feature."
			)
			return

		if suit_image is None:
			self.status_var.set(
				"Не удалось выделить suit feature."
			)
			return

		rank_saved = self._save_template(
			"ranks",
			rank,
			rank_image,
		)

		suit_saved = self._save_template(
			"suits",
			suit,
			suit_image,
		)

		self._save_record(
			status="accepted",
			label=label,
		)

		self.guesser.reload()
		self._refresh_dictionary_progress()

		if rank_saved or suit_saved:
			self.status_var.set(
				f"Сохранено: {label}"
			)
		else:
			self.status_var.set(
				f"{label}: такие feature уже были."
			)

		self._move_to_index(
			self.index + 1
		)

	def _skip_sample(self):
		self._save_record(
			status="skipped",
			label=self._real_label(),
		)

		self._move_to_index(
			self.index + 1
		)

	def _save_template(
		self,
		category,
		label,
		image,
	):
		folder = (
			self.template_root
			/ category
			/ label
		)

		folder.mkdir(
			parents=True,
			exist_ok=True,
		)

		ok, encoded = cv2.imencode(
			".png",
			image,
		)

		if not ok:
			return False

		digest = hashlib.sha1(
			encoded.tobytes()
		).hexdigest()[:16]

		path = (
			folder
			/ f"{digest}.png"
		)

		if path.exists():
			return False

		return bool(
			cv2.imwrite(
				str(path),
				image,
			)
		)

	def _refresh_dictionary_progress(self):
		self.rank_counts = {
			rank: self._template_count(
				"ranks",
				rank,
			)
			for rank in VALID_RANKS
		}

		self.suit_counts = {
			suit: self._template_count(
				"suits",
				suit,
			)
			for suit in VALID_SUITS
		}

		rank_ready = sum(
			count >= RANK_READY_TARGET
			for count in self.rank_counts.values()
		)

		rank_good = sum(
			count >= RANK_GOOD_TARGET
			for count in self.rank_counts.values()
		)

		rank_minimum = sum(
			count >= RANK_MINIMUM_TARGET
			for count in self.rank_counts.values()
		)

		weak_ranks = [
			rank
			for rank, count
			in self.rank_counts.items()
			if count < RANK_MINIMUM_TARGET
		]

		self.rank_summary_var.set(
			f"Готово {rank_ready}/13 · "
			f"≥8: {rank_good}/13 · "
			f"≥4: {rank_minimum}/13\n"
			f"Слабые: {' '.join(weak_ranks) or 'нет'}"
		)

		suit_ready = sum(
			count >= SUIT_READY_TARGET
			for count in self.suit_counts.values()
		)

		suit_good = sum(
			count >= SUIT_GOOD_TARGET
			for count in self.suit_counts.values()
		)

		suit_minimum = sum(
			count >= SUIT_MINIMUM_TARGET
			for count in self.suit_counts.values()
		)

		weak_suits = [
			suit
			for suit, count
			in self.suit_counts.items()
			if count < SUIT_MINIMUM_TARGET
		]

		self.suit_summary_var.set(
			f"Готово {suit_ready}/4 · "
			f"≥18: {suit_good}/4 · "
			f"≥8: {suit_minimum}/4\n"
			f"Слабые: {' '.join(weak_suits) or 'нет'}"
		)

		self._draw_rank_progress()
		self._draw_suit_progress()

	def _template_count(
		self,
		category,
		label,
	):
		folder = (
			self.template_root
			/ category
			/ label
		)

		if not folder.exists():
			return 0

		return len(
			list(
				folder.glob(
					"*.png"
				)
			)
		)

	def _draw_rank_progress(self):
		if not hasattr(
			self,
			"rank_canvas",
		):
			return

		self._draw_progress_grid(
			self.rank_canvas,
			VALID_RANKS,
			self.rank_counts,
			RANK_READY_TARGET,
			RANK_GOOD_TARGET,
			RANK_MINIMUM_TARGET,
			columns=4,
		)

	def _draw_suit_progress(self):
		if not hasattr(
			self,
			"suit_canvas",
		):
			return

		self._draw_progress_grid(
			self.suit_canvas,
			VALID_SUITS,
			self.suit_counts,
			SUIT_READY_TARGET,
			SUIT_GOOD_TARGET,
			SUIT_MINIMUM_TARGET,
			columns=2,
		)

	def _draw_progress_grid(
		self,
		canvas,
		labels,
		counts,
		ready_target,
		good_target,
		minimum_target,
		columns,
	):
		canvas.delete(
			"all"
		)

		width = max(
			360,
			canvas.winfo_width(),
		)

		cell_width = (
			width - 12
		) // columns

		cell_height = 54

		for index, label in enumerate(
			labels
		):
			row = index // columns
			column = index % columns

			x = 6 + column * cell_width
			y = 6 + row * cell_height

			count = counts.get(
				label,
				0,
			)

			progress = min(
				1.0,
				count / float(
					ready_target
				),
			)

			if count >= ready_target:
				color = "#34c759"
				state = "✓"
			elif count >= good_target:
				color = "#9acd32"
				state = "○"
			elif count >= minimum_target:
				color = "#f0b429"
				state = "·"
			else:
				color = "#d9534f"
				state = "!"

			canvas.create_rectangle(
				x,
				y,
				x + cell_width - 7,
				y + 45,
				outline="#444444",
				fill="#202020",
			)

			canvas.create_text(
				x + 8,
				y + 13,
				text=label,
				fill="#f2f2f2",
				font=(
					"Consolas",
					13,
					"bold",
				),
				anchor="w",
			)

			canvas.create_text(
				x + cell_width - 16,
				y + 13,
				text=f"{state}{count}",
				fill=color,
				font=(
					"Consolas",
					10,
					"bold",
				),
				anchor="e",
			)

			canvas.create_text(
				x + 8,
				y + 28,
				text=(
					f"{int(progress * 100)}% "
					f"из {ready_target}"
				),
				fill="#aaaaaa",
				font=(
					"Segoe UI",
					8,
				),
				anchor="w",
			)

			bar_width = int(
				(cell_width - 10)
				* progress
			)

			if bar_width > 0:
				canvas.create_rectangle(
					x + 2,
					y + 38,
					x + 2 + bar_width,
					y + 43,
					outline="",
					fill=color,
				)

		rows = (
			len(labels)
			+ columns - 1
		) // columns

		canvas.configure(
			height=rows * cell_height + 10
		)

	def _draw_features(self):
		if self.card_image is None:
			return

		rank = rank_feature(
			self.card_image
		)

		suit = suit_feature(
			self.card_image
		)

		self.rank_photo = self._feature_photo(
			rank,
			180,
			150,
		)

		self.suit_photo = self._feature_photo(
			suit,
			180,
			150,
		)

		if self.rank_photo is not None:
			self.rank_feature_label.configure(
				image=self.rank_photo,
				text="",
			)

		if self.suit_photo is not None:
			self.suit_feature_label.configure(
				image=self.suit_photo,
				text="",
			)

	def _feature_photo(
		self,
		image,
		width,
		height,
	):
		if image is None:
			return None

		pil = Image.fromarray(
			image
		).convert(
			"L"
		)

		pil.thumbnail(
			(
				width,
				height,
			),
			Image.Resampling.NEAREST,
		)

		return ImageTk.PhotoImage(
			pil
		)

	def _redraw_card(self):
		if self.card_image is None:
			return

		canvas_width = max(
			1,
			self.card_canvas.winfo_width(),
		)

		canvas_height = max(
			1,
			self.card_canvas.winfo_height(),
		)

		image_height, image_width = (
			self.card_image.shape[:2]
		)

		scale = min(
			(canvas_width - 30)
			/ max(
				image_width,
				1,
			),
			(canvas_height - 30)
			/ max(
				image_height,
				1,
			),
		)

		scale = max(
			1.0,
			min(
				scale,
				8.0,
			),
		)

		width = int(
			round(
				image_width * scale
			)
		)

		height = int(
			round(
				image_height * scale
			)
		)

		rgb = cv2.cvtColor(
			self.card_image,
			cv2.COLOR_BGR2RGB,
		)

		pil = Image.fromarray(
			rgb
		).resize(
			(
				width,
				height,
			),
			Image.Resampling.NEAREST,
		)

		self.card_photo = (
			ImageTk.PhotoImage(
				pil
			)
		)

		self.card_canvas.delete(
			"all"
		)

		self.card_canvas.create_image(
			canvas_width // 2,
			canvas_height // 2,
			image=self.card_photo,
			anchor="center",
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

	def _on_mousewheel(
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
				len(self.samples) - 1,
			),
		)

		self._load_current_sample()

	def _update_navigation(self):
		if self.index <= 0:
			self.previous_button.state(
				["disabled"]
			)
		else:
			self.previous_button.state(
				["!disabled"]
			)

		if self.index >= len(
			self.samples
		) - 1:
			self.next_button.state(
				["disabled"]
			)
		else:
			self.next_button.state(
				["!disabled"]
			)

		self._update_accept_button()

	def _update_accept_button(self):
		if self._is_valid_label(
			self._real_label()
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
		label,
	):
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
			"label": label,
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
			self.samples
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
				len(self.samples) - 1,
			),
		)

	def _quit(self):
		self.state[
			"last_index"
		] = self.index

		self._save_state()
		self.root.destroy()


def collect_samples(
	project_root,
):
	return sorted(
		(
			project_root
			/ "captures"
		).glob(
			"table_*/cards/*.png"
		)
	)


def main():
	project_root = find_project_root()
	samples = collect_samples(
		project_root
	)

	if not samples:
		print(
			"No captured card samples found."
		)
		return

	root = tk.Tk()

	CardLabelerApp(
		root,
		project_root,
		samples,
	)

	root.mainloop()


if __name__ == "__main__":
	main()
