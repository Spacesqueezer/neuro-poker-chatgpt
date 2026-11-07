"""Tk capture loop, independent card/text workers and bounded evidence recording."""

import json
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

import cv2
import mss
import numpy as np

from poker.hud.bet_bridge import BetBridge
from poker.hud.context import analyze_names
from poker.hud.decision_observer import fast_decision_draft
from poker.hud.decision_stream import DecisionStream, blocker_comment
from poker.hud.diagnostics import Recorder
from poker.hud.fast_table import analyze_fast_table
from poker.hud.hand import HandObservation, HandTracker
from poker.hud.layout import overlap, place_card
from poker.hud.live_evidence import LiveEvidence
from poker.hud.odds import CATEGORIES
from poker.hud.pipeline import analyze_frame, my_turn
from poker.hud.player_store import LiveCollector, PlayerStore
from poker.hud.presentation import card_text, hand_text, name_color, stack_text
from poker.hud.recognition import configure_ocr
from poker.hud.seat_occupancy import clear_empty_identities
from poker.hud.session_images import saved_frame_path
from poker.hud.state import TableState
from poker.hud.storage import create_log, read_statistics, save_capture
from poker.hud.title_stakes import title_stakes_comment
from poker.hud.ui_settings import load_settings, panel_position, save_settings
from poker.hud.windows import Desktop, outside_work_area


class HudApp:
    def __init__(self, root_path: Path, database=None, stats_file=None):
        self.path, self.database = root_path, database
        self.settings_path = root_path / "data/hud/ui.json"
        self.ui_settings = load_settings(self.settings_path)
        self.drag = None
        self.monitor_slots = []
        self.action_labels = {}
        self.observed_actions = 0
        self.log, self.log_path = create_log(root_path / "artifacts/hud/logs")
        self.player_store = PlayerStore(stats_file or root_path / "data/hud/players.sqlite3")
        self.desktop = Desktop()
        self.root = tk.Tk()
        self.root.title("Neuro HUD — управление")
        self.root.configure(bg="#15202d")
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.report_callback_exception = self.callback_error
        self.state = TableState(self.player_store.resolve_name)
        self.hand = HandObservation()
        self.hand_tracker = HandTracker()
        self.decision_stream = DecisionStream()
        self.live_evidence = LiveEvidence()
        self.hand_confirmed = False
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hud-cards")
        self.names_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hud-names")
        self.fast_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hud-table")
        self.fast_future = None
        self.fast_context = None
        self.fast_evidence = LiveEvidence()
        self.capture_epoch = self.live_evidence.epoch
        self.cards_meta = {}
        self.bet_bridge = BetBridge()
        self.last_fast = 0.0
        self.names_future = None
        self.names_context = None
        self.names_meta = {}
        self.last_names = 0.0
        self.recorder = Recorder(root_path / "artifacts/hud/sessions")
        self.stats_collector = LiveCollector(self.player_store, self.recorder.path.name + ":0")
        self.stats_status = tk.StringVar(value="Статистика: запись включена")
        self.mouse_down = (False, False)
        self.last_frame_id = None
        self.record_status = tk.StringVar(value="Запись диагностики включена")
        self.capture = mss.mss()
        self.future = None
        self.frame_context = None
        self.target = None
        self.pending_capture = False
        self.paused = False
        self.closed = False
        self.last_scan = 0.0
        self.last_summary = None
        self.last_heartbeat = 0.0
        self.activity = None
        self.last_draw = None
        self.cards = {}
        self.exclusion_ok = True
        self.generation = 0
        self.rois = tk.BooleanVar(value=True)
        self.hero_seat = self.ui_settings["hero_seat"]
        self.auto_size_table = tk.BooleanVar(value=self.ui_settings["auto_size_table"])
        self.status = tk.StringVar(value="Выберите окно стола")
        self.selection = ttk.Combobox(self.root, state="readonly", width=44)
        self.selection.grid(row=0, column=0, columnspan=4, padx=8, pady=6)
        self.selection.bind("<<ComboboxSelected>>", self.select)
        ttk.Checkbutton(
            self.root,
            text="Размер стола автоматически (при выборе окна)",
            variable=self.auto_size_table,
            command=self.change_auto_size,
        ).grid(row=10, column=0, columnspan=5, sticky="w", padx=8)
        ttk.Label(self.root, text="Место героя:").grid(row=11, column=0, sticky="w", padx=8)
        self.hero_selection = ttk.Combobox(
            self.root,
            state="readonly",
            values=(
                "Сверху слева",
                "Сверху справа",
                "Слева",
                "Справа",
                "Слева внизу",
                "Справа внизу",
                "По центру внизу",
            ),
        )
        self.hero_selection.current(self.hero_seat)
        self.hero_selection.grid(row=11, column=1, columnspan=4, sticky="ew", padx=8)
        self.hero_selection.bind("<<ComboboxSelected>>", self.change_hero_seat)
        ttk.Button(self.root, text="Окна ↻", command=self.refresh).grid(row=0, column=4, padx=6)
        self.capture_button = ttk.Button(self.root, text="📷 Снимок", command=self.request_capture)
        self.capture_button.grid(row=1, column=0, padx=6, pady=5)
        ttk.Checkbutton(self.root, text="ROI", variable=self.rois, command=self.draw).grid(
            row=1, column=1
        )
        self.pause_button = ttk.Button(self.root, text="Пауза", command=self.toggle_pause)
        self.pause_button.grid(row=1, column=2)
        ttk.Button(self.root, text="Логи", command=self.show_log).grid(row=1, column=3)
        ttk.Button(self.root, text="Выход", command=self.close).grid(row=1, column=4)
        ttk.Label(self.root, textvariable=self.status, wraplength=520).grid(
            row=2, column=0, columnspan=5, sticky="w", padx=8, pady=5
        )
        ttk.Button(self.root, text="⚑ Заметка", command=self.add_note).grid(row=3, column=0)
        ttk.Label(self.root, textvariable=self.record_status, wraplength=430).grid(
            row=3, column=1, columnspan=4, sticky="w"
        )
        ttk.Button(self.root, text="Копия БД", command=self.backup_statistics).grid(row=4, column=0)
        ttk.Label(self.root, textvariable=self.stats_status, wraplength=430).grid(
            row=4, column=1, columnspan=4, sticky="w"
        )
        self.transparency = tk.DoubleVar(value=self.ui_settings["transparency"])
        self.transparency_text = tk.StringVar(value=f"Прозрачность: {self.transparency.get():.0f}%")
        ttk.Label(self.root, textvariable=self.transparency_text).grid(row=5, column=0)
        slider = ttk.Scale(
            self.root, from_=0, to=80, variable=self.transparency, command=self.change_transparency
        )
        slider.grid(row=5, column=1, columnspan=3, sticky="ew", padx=6)
        slider.bind("<ButtonRelease-1>", lambda _: self.persist_ui())
        ttk.Button(self.root, text="Сброс позиций", command=self.reset_positions).grid(
            row=5, column=4
        )
        ttk.Label(
            self.root, text="Панели: перетащить левой кнопкой; короткий клик — исправить ник"
        ).grid(row=6, column=0, columnspan=5)
        self.monitor_status = tk.StringVar(value="Нейросеть выключена · наблюдение: ждём стол")
        ttk.Label(self.root, textvariable=self.monitor_status, wraplength=650).grid(
            row=7, column=0, columnspan=5, sticky="w", padx=8
        )
        self.capture_notice = tk.StringVar(value="")
        self.capture_notice_key = None
        ttk.Label(
            self.root, textvariable=self.capture_notice, foreground="#d97706", wraplength=650
        ).grid(row=8, column=0, columnspan=5, sticky="w", padx=8)
        self.layer = tk.Toplevel(self.root)
        self.layer.overrideredirect(True)
        self.layer.attributes("-topmost", True)
        self.layer.attributes("-transparentcolor", "#ff00ff")
        self.canvas = tk.Canvas(self.layer, bg="#ff00ff", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.exclusion_ok &= self.desktop.configure_overlay(self.layer, click_through=True)
        self.exclusion_ok &= self.desktop.configure_overlay(self.root)
        self.layer.withdraw()
        self.hand_panel = tk.Toplevel(self.root)
        self.hand_panel.overrideredirect(True)
        self.hand_panel.attributes("-topmost", True)
        self.hand_label = tk.Label(
            self.hand_panel,
            bg="#142130",
            fg="#e8f2ff",
            font=("Segoe UI", 10),
            padx=12,
            pady=9,
            justify="left",
            wraplength=370,
            cursor="hand2",
        )
        self.hand_label.pack(fill="both", expand=True)
        self.hand_label.bind("<Button-1>", lambda _: self.show_odds())
        self.exclusion_ok &= self.desktop.configure_overlay(self.hand_panel)
        self.hand_panel.withdraw()
        self.refresh()
        self.log.info(
            "START version=2 log=%s capture_exclusion=%s database=%s",
            self.log_path,
            self.exclusion_ok,
            database,
        )
        try:
            version = configure_ocr()
            self.recorder.event(
                "runtime",
                {
                    "tesseract": version,
                    "opencv": cv2.__version__,
                    "capture_exclusion": self.exclusion_ok,
                    "log": str(self.log_path),
                },
                "Среда OCR настроена; подробности версий записаны.",
            )
        except Exception:
            self.log.exception("OCR_UNAVAILABLE")
            messagebox.showerror("Tesseract OCR", "Не найден Tesseract. Подробности в логе.")
            self.close()
            return
        self.root.after(150, self.tick)
        self.root.after(20, self.poll_mouse)

    def callback_error(self, exception, value, traceback):
        self.log.error("UI_ERROR", exc_info=(exception, value, traceback))
        self.status.set(f"Ошибка: {value}. Подробности в логе.")

    def refresh(self):
        self.windows = self.desktop.windows()
        self.selection["values"] = [
            f"{window.title} [0x{window.handle:x}]" for window in self.windows
        ]
        self.selection.set("")

    def select(self, _=None):
        index = self.selection.current()
        if index < 0:
            return
        self.target = self.windows[index]
        if self.auto_size_table.get():
            try:
                result = self.desktop.fit_table(self.target.handle)
                self.recorder.event(
                    "table_auto_size", result, "Автоподбор размера стола: " + result["status"]
                )
            except OSError as error:
                self.log.warning("TABLE_AUTO_SIZE %s", error)
                self.recorder.event(
                    "table_auto_size",
                    {"status": "failed", "error": str(error)},
                    "Не удалось изменить размер стола; оставлен текущий.",
                )
        self.generation += 1
        self.reset_capture_evidence()
        self.decision_stream.reset()
        self.stats_collector = LiveCollector(
            self.player_store, f"{self.recorder.path.name}:{self.generation}"
        )
        self.last_names = 0
        self.names_meta = {}
        self.monitor_slots = []
        self.action_labels = {}
        self.drag = None
        self.capture_notice_key = None
        self.capture_notice.set("")
        self.monitor_status.set("Нейросеть выключена · наблюдение: ждём новый стол")
        self.recorder.event(
            "target",
            {"window": self.target.title, "generation": self.generation},
            "Выбрано окно: " + self.target.title,
        )
        self.state = TableState(self.player_store.resolve_name)
        self.hand = HandObservation()
        self.hand_tracker = HandTracker()
        self.hand_confirmed = False
        self.hide()
        for card in self.cards.values():
            card.destroy()
        self.cards.clear()
        self.pending_capture = False
        self.capture_button.configure(text="📷 Снимок")
        self.status.set("Ожидание активного окна стола…")
        self.log.info("TARGET handle=%s title=%s", self.target.handle, self.target.title)

    def request_capture(self):
        if not self.target:
            self.status.set("Сначала выберите окно стола")
            return
        self.pending_capture = True
        self.capture_button.configure(text="Сохраняется…")
        self.last_scan = 0
        self.log.info("CAPTURE_REQUEST")

    def toggle_pause(self):
        self.reset_capture_evidence()
        self.decision_stream.reset()
        self.paused = not self.paused
        self.pause_button.configure(text="Продолжить" if self.paused else "Пауза")
        self.log.info("PAUSE %s", self.paused)
        self.recorder.event(
            "pause", {"paused": self.paused}, "Пауза" if self.paused else "Работа возобновлена"
        )
        if self.paused:
            self.hide()

    def show_log(self):
        self.reset_capture_evidence()
        self.decision_stream.reset()
        was_paused, self.paused = self.paused, True
        try:
            messagebox.showinfo(
                "Диагностика HUD",
                f"Лог:\n{self.log_path}\n\nАвтоматическая диагностика:\n{self.recorder.path}"
                "\n\nЧитайте timeline.md; свои пояснения — в comments.md.",
            )
        finally:
            self.paused = was_paused

    def hide(self):
        self.last_draw = None
        self.layer.withdraw()
        self.hand_panel.withdraw()
        for card in self.cards.values():
            card.withdraw()

    def tick(self):
        if self.closed:
            return
        try:
            self.record_status.set(self.recorder.status())
            if self.future and self.future.done():
                future, self.future = self.future, None
                frame, meta, generation, started, requested = self.frame_context
                try:
                    analysis = future.result()
                    observations = [
                        s.observation for s in self.state.seats.values() if not s.missing
                    ]
                except Exception as error:
                    self.recorder.event(
                        "card_error",
                        {**meta, "error": str(error)},
                        "Ошибка чтения карт: " + str(error),
                    )
                    if requested and generation == self.generation:
                        directory = save_capture(
                            self.path / "captures", frame, [], {**meta, "ocr_error": str(error)}
                        )
                        self.log.info("CAPTURE_SAVED_WITH_OCR_ERROR %s", directory)
                    raise
                if generation == self.generation and meta["evidence_epoch"] == self.capture_epoch:
                    frame_size = (frame.shape[1], frame.shape[0])
                    if self.state.size and self.state.size != frame_size:
                        self.hand_tracker.update(HandObservation())
                    if analysis.hand.my_turn and not self.hand.my_turn:
                        self.last_fast = 0.0  # Decision facts do not wait for nickname OCR.
                    self.hand = analysis.hand
                    self.cards_meta = {**meta, "hand": self.hand.to_dict()}
                    if not self.hand.my_turn:
                        self.decision_stream.reset()
                    self.hand_confirmed = self.hand_tracker.update(self.hand)
                    if self.state.size and self.state.size != frame_size:
                        self.state = TableState(self.player_store.resolve_name)
                    summary = [
                        (s.key, s.name, s.observation.stack, s.observation.status, s.conflict)
                        for s in self.state.seats.values()
                    ]
                    summary.append(
                        (
                            self.hand.hero,
                            self.hand.board,
                            self.hand.phase,
                            self.hand.valid,
                            self.hand_confirmed,
                        )
                    )
                    changed = summary != self.last_summary
                    self.recorder.event(
                        "cards",
                        {
                            **meta,
                            "hand": self.hand.to_dict(),
                            "confirmed": self.hand_confirmed,
                            "local_hand": self.hand_tracker.hand_number,
                            "processing_ms": analysis.elapsed_ms,
                            "result_latency_ms": round((time.monotonic() - started) * 1000, 1),
                        },
                        (
                            f"{self.hand.street}: {self.hand.phase}. "
                            f"Герой {card_text(self.hand.hero)}; "
                            f"борд {card_text(self.hand.board)}. {self.hand.issue}"
                        )
                        if changed
                        else "",
                    )
                    if changed:
                        self.log.info(
                            "OBSERVATION elapsed_ms=%d players=%s",
                            (time.monotonic() - started) * 1000,
                            json.dumps([p.to_dict() for p in observations], ensure_ascii=False),
                        )
                        self.last_summary = summary
                        self.log.info(
                            "HAND confirmed=%s local_hand=%s data=%s",
                            self.hand_confirmed,
                            self.hand_tracker.hand_number,
                            json.dumps(self.hand.to_dict(), ensure_ascii=False),
                        )
                    self.status.set(
                        f"Игроков: {len(observations)} · карты {analysis.elapsed_ms:.0f} мс"
                        " · имя: нажмите панель"
                    )
                    if requested:
                        meta["names_source"] = self.names_meta
                        meta["diagnostics"] = str(self.recorder.path)
                        meta["hand"] = self.hand.to_dict()
                        meta["hand_confirmed"] = self.hand_confirmed
                        meta["local_hand_number"] = self.hand_tracker.hand_number
                        meta["identities"] = [
                            {
                                "seat": s.key,
                                "name": s.name,
                                "manual": s.manual,
                                "conflict": s.conflict,
                            }
                            for s in self.state.seats.values()
                        ]
                        directory = save_capture(self.path / "captures", frame, observations, meta)
                        self.log.info("CAPTURE_SAVED %s", directory)
                        self.status.set(f"Снимок сохранён: {directory.name}")
                        self.capture_button.configure(text="📷 Снимок")
            self.collect_fast_table()
            self.collect_names()
            rect = self.desktop.rect(self.target.handle) if self.target else None
            active = bool(rect and self.desktop.own_foreground(self.target.handle))
            activity = (active, self.paused, rect)
            if activity != self.activity:
                self.reset_capture_evidence()
                self.log.info("WINDOW_STATE active=%s paused=%s rect=%s", *activity)
                self.activity = activity
                self.recorder.event(
                    "window",
                    {"active": active, "paused": self.paused, "rect": rect},
                    f"Окно: активно={active}, пауза={self.paused}, область={rect}",
                )
                if not active or self.paused:
                    self.monitor_status.set("Нейросеть выключена · наблюдение приостановлено")
                    self.decision_stream.reset()
                    self.hand = HandObservation()
                    self.hand_confirmed = False
                    self.hand_tracker.update(self.hand)
                if not active:
                    self.status.set("Ожидание: откройте выбранный стол поверх других окон")
                elif self.paused:
                    self.status.set("Пауза")
            if time.monotonic() - self.last_heartbeat > 10:
                self.log.info(
                    "HEARTBEAT active=%s paused=%s ocr_busy=%s seats=%d",
                    active,
                    self.paused,
                    bool(self.future),
                    len(self.state.seats),
                )
                self.last_heartbeat = time.monotonic()
            if not active or self.paused:
                self.hide()
            else:
                self.draw()
            if (
                active
                and (not self.paused or self.pending_capture)
                and time.monotonic() - self.last_scan >= 0.25
            ):
                self.scan(rect)
        except Exception as error:
            self.hand_confirmed = False
            self.hand = HandObservation(phase="Ошибка распознавания")
            self.hand_tracker.update(self.hand)
            self.hide()
            self.log.exception("SCAN_ERROR")
            self.recorder.event(
                "error",
                {"error": str(error), "frame_id": self.last_frame_id},
                "Ошибка распознавания: " + str(error),
            )
            self.status.set(f"Ошибка: {error}. Подробности в логе.")
            self.capture_button.configure(text="📷 Снимок")
            self.last_scan = time.monotonic() + 3
        finally:
            if not self.closed:
                self.root.after(50, self.tick)

    def scan(self, rect):
        assert self.target is not None, "Capture requires a selected window"
        capture_started = time.monotonic()
        x, y, width, height = rect
        if not self.exclusion_ok:
            # Compatibility fallback: never feed our own labels into OCR.
            self.hide()
            self.root.withdraw()
            self.root.update_idletasks()
            time.sleep(0.04)
        try:
            title_before = self.desktop.title(self.target.handle)
            raw = np.asarray(
                self.capture.grab({"left": x, "top": y, "width": width, "height": height})
            )
            frame = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)
            title_after = self.desktop.title(self.target.handle)
        finally:
            if not self.exclusion_ok:
                self.root.deiconify()
        self.last_scan = time.monotonic()
        meta = {
            "captured_at": datetime.now(UTC).isoformat(),
            "window": self.target.title,
            "window_handle": self.target.handle,
            "window_title_capture": {"before": title_before, "after": title_after},
            "client_rect": rect,
            "log": str(self.log_path),
            "capture_ms": round((time.monotonic() - capture_started) * 1000, 1),
        }
        work = self.desktop.work_area(self.target.handle)
        overflow = outside_work_area(rect, work) if work else None
        meta["capture_geometry"] = {"work_area": work, "overflow": overflow}
        warning = bool(overflow and any(overflow.values()))
        self.capture_notice.set(
            "Окно выходит за рабочую область монитора. Уменьшите или переместите его, "
            "чтобы нижние кнопки и поле ставки были видны целиком."
            if warning
            else ""
        )
        key = (tuple(work or []), warning)
        if key != self.capture_notice_key:
            self.capture_notice_key = key
            self.recorder.event(
                "capture_geometry",
                meta,
                self.capture_notice.get()
                if warning
                else "Окно находится в рабочей области монитора."
                if work
                else "Рабочая область монитора неизвестна.",
            )
        names_interval = 3.0
        fast_interval = 0.25 if my_turn(frame) else 0.75
        names_due = not self.names_future and time.monotonic() - self.last_names >= names_interval
        fast_due = (
            not self.paused
            and not self.fast_future
            and time.monotonic() - self.last_fast >= fast_interval
        )
        meta["hero_seat"] = self.hero_seat
        self.last_frame_id = self.recorder.frame(
            frame,
            meta,
            force_image=bool(names_due or fast_due),
            lossless=bool(names_due or fast_due),
        )
        meta["frame_id"] = self.last_frame_id
        meta["evidence_epoch"] = self.capture_epoch
        if not self.future:
            self.frame_context = frame, meta, self.generation, self.last_scan, self.pending_capture
            self.pending_capture = False
            self.future = self.pool.submit(analyze_frame, frame, False, self.hero_seat)
        if names_due:
            self.last_names = time.monotonic()
            self.names_context = meta.copy(), self.generation, (width, height), frame
            self.names_future = self.names_pool.submit(analyze_names, frame, self.hero_seat)
        if fast_due:
            self.last_fast = time.monotonic()
            self.fast_context = meta.copy(), self.generation, frame
            self.fast_future = self.fast_pool.submit(analyze_fast_table, frame, self.hero_seat)

    def reset_capture_evidence(self):
        """Only real capture/UI boundaries invalidate both asynchronous streams."""
        self.capture_epoch += 1
        self.live_evidence.reset()
        self.fast_evidence.reset()
        self.live_evidence.epoch = self.fast_evidence.epoch = self.capture_epoch
        self.decision_stream.reset()
        self.bet_bridge = BetBridge()
        self.cards_meta = {}

    def reset_names_evidence(self):
        self.live_evidence.reset()
        self.live_evidence.epoch = self.capture_epoch

    def collect_fast_table(self):
        if not self.fast_future or not self.fast_future.done():
            return
        future, self.fast_future = self.fast_future, None
        meta, generation, frame = self.fast_context
        try:
            context = future.result()
        except Exception as error:
            self.fast_evidence.reset()
            self.bet_bridge = BetBridge()
            self.decision_stream.reset()
            self.recorder.event(
                "fast_table_error",
                {**meta, "error": str(error)},
                "Ошибка быстрого чтения стола: " + str(error),
            )
            return
        valid = (
            not self.paused
            and self.target is not None
            and generation == self.generation
            and meta["evidence_epoch"] == self.capture_epoch
            and self.desktop.own_foreground(self.target.handle)
            and tuple(self.desktop.rect(self.target.handle) or ()) == tuple(meta["client_rect"])
        )
        if self.fast_evidence.epoch != self.capture_epoch:
            self.fast_evidence.reset()
            self.fast_evidence.epoch = self.capture_epoch
        facts = None
        if valid:
            facts = self.fast_evidence.update(
                context,
                {
                    **meta,
                    "image": str(saved_frame_path(self.recorder.path, meta["frame_id"]).resolve()),
                },
            )
        if facts is None:
            self.fast_evidence.reset()
            self.bet_bridge = BetBridge()
            self.decision_stream.reset()
        else:
            facts = self.bet_bridge.augment(
                {
                    **meta,
                    "image": str(saved_frame_path(self.recorder.path, meta["frame_id"]).resolve()),
                },
                context,
                facts,
            )
            self.bet_bridge.add(
                {
                    **meta,
                    "image": str(saved_frame_path(self.recorder.path, meta["frame_id"]).resolve()),
                },
                context,
                facts,
            )
        action_count = sum(bool(s.get("action_label")) for s in context["table_signals"]["slots"])
        self.recorder.event(
            "fast_table",
            {
                **meta,
                "context": context,
                "evidence": facts,
                "accepted": facts is not None,
                "model_called": False,
                "recording_status": {
                    "limited": self.recorder.limit_reached,
                    "dropped": self.recorder.dropped,
                    "error": self.recorder.error,
                },
            },
            f"Частое чтение стола: ставок подтверждено {len(facts['bet_confirmations'])}; "
            f"подписей действий {action_count}."
            if facts is not None
            else "Частое чтение стола: результат отклонён после разрыва наблюдений.",
        )
        if facts is not None:
            draft = fast_decision_draft(
                context,
                {
                    **meta,
                    "image": str(saved_frame_path(self.recorder.path, meta["frame_id"]).resolve()),
                },
                facts,
                self.fast_evidence.tracker,
                self.decision_stream,
                latest_cards=self.cards_meta,
            )
            if draft:
                reason_count = len(draft["advisor"]["blockers"])
                self.recorder.event(
                    "decision_dry_run",
                    draft,
                    "Быстрый пробный запрос: отправка заблокирована — "
                    + blocker_comment(draft["blockers"])
                    + f". Контракт советника: {reason_count} причин блокировки. "
                    + title_stakes_comment(facts.get("table_stakes", {})),
                    frame=frame.copy(),
                )

    def collect_names(self):
        if not self.names_future or not self.names_future.done():
            return
        future, self.names_future = self.names_future, None
        meta, generation, size, frame = self.names_context
        try:
            observations, context = future.result()
        except Exception as error:
            self.log.exception("NAMES_ERROR")
            self.reset_names_evidence()
            self.recorder.event(
                "error", {**meta, "error": str(error)}, "Ошибка чтения текста: " + str(error)
            )
            return
        rect = self.desktop.rect(self.target.handle) if self.target else None
        if generation != self.generation or not rect or rect[2:] != size:
            return
        if (
            self.paused
            or not self.desktop.own_foreground(self.target.handle)
            or tuple(rect) != tuple(meta["client_rect"])
        ):
            self.reset_names_evidence()
            return
        if meta["evidence_epoch"] != self.capture_epoch:
            return
        if self.live_evidence.epoch != self.capture_epoch:
            self.reset_names_evidence()
        facts = self.live_evidence.update(
            context,
            {
                **meta,
                "image": str(saved_frame_path(self.recorder.path, meta["frame_id"]).resolve()),
            },
            [p.to_dict() for p in observations],
        )
        if facts is None:
            self.monitor_status.set(
                "Нейросеть выключена · ждём свежий OCR после разрыва наблюдений"
            )
            self.recorder.event(
                "live_evidence_rejected",
                {**meta, "current_epoch": self.capture_epoch},
                "Подтверждения не приняты: устаревший результат OCR или прерванный захват.",
            )
            self.recorder.event(
                "names",
                {
                    **meta,
                    "players": [p.to_dict() for p in observations],
                    "context": context,
                    "live_evidence_rejected": True,
                },
                "Сырой OCR сохранён для разбора; живое состояние не обновлено.",
            )
            return
        facts = self.bet_bridge.augment(
            {
                **meta,
                "image": str(saved_frame_path(self.recorder.path, meta["frame_id"]).resolve()),
            },
            context,
            facts,
        )
        facts["recording_status"] = {
            "limited": self.recorder.limit_reached,
            "dropped": self.recorder.dropped,
            "error": self.recorder.error,
        }
        self.recorder.event(
            "live_evidence",
            {**meta, **facts},
            f"Подтверждено участие: {len(facts['participation_evidence'])}; "
            f"ставок: {len(facts['bet_confirmations'])}; "
            f"стеков: {len(facts['stack_confirmations'])}; "
            "минимальная сумма на улице: "
            f"{facts.get('min_raise_confirmation', {}).get('value', 'не подтверждена')}; "
            "максимальная сумма на улице: "
            f"{facts.get('max_raise_confirmation', {}).get('value', 'не подтверждена')}. "
            "Нейросеть выключена.",
        )
        self.state.update(observations, size)
        cleared = clear_empty_identities(
            self.state,
            context.get("table_signals", {}).get("slots", []),
            facts.get("empty_seat_confirmations", {}),
        )
        if cleared:
            self.recorder.event(
                "empty_seat_identity_cleared",
                {**meta, "seat_keys": cleared},
                "Подтверждено пустое место: прежняя привязка ника снята с HUD, "
                "запись игрока в БД сохранена.",
            )
        self.names_meta = meta
        self.update_monitor(context, meta)
        self.monitor_status.set(
            self.monitor_status.get()
            + f"\nПодтверждено: участников {len(facts['participation_evidence'])}, "
            f"ставок {len(facts['bet_confirmations'])}, стеков {len(facts['stack_confirmations'])}"
        )
        try:
            self.stats_collector.observe(context, self.state, meta)
            self.stats_status.set(self.stats_collector.status)
        except Exception:
            self.log.exception("PLAYER_STATISTICS_WRITE_ERROR")
            self.stats_status.set("Статистика: ошибка записи, см. лог")
        uncertain = [p.raw_name or "?" for p in observations if not p.name or p.confidence < 90]
        self.recorder.event(
            "names",
            {
                **meta,
                "players": [p.to_dict() for p in observations],
                "context": context,
                "uncertain": uncertain,
            },
            "Игроки: "
            + "; ".join(
                f"{p.name or '?'} ({p.confidence:.0f}), стек {p.stack or '?'}" for p in observations
            )
            + (". Проверить OCR: " + ", ".join(uncertain) if uncertain else ""),
        )
        self.recorder.event(
            "table_context",
            {**meta, **context},
            f"Кандидатов баттона: {len(context['dealer_candidates'])}. "
            "Сырые надписи стола: " + context["regions"]["table_text"]["raw_text"],
        )
        if context["errors"]:
            self.recorder.event(
                "context_error",
                {**meta, "errors": context["errors"]},
                "Ошибка диагностического OCR: " + "; ".join(context["errors"]),
            )

    def poll_mouse(self):
        if self.closed:
            return
        try:
            if self.target:
                down, position = self.desktop.mouse_sample(self.target.handle)
                if position and not self.paused:
                    for i, button in enumerate(("left", "right")):
                        if down[i] and not self.mouse_down[i]:
                            self.recorder.event(
                                "click",
                                {
                                    **position,
                                    "button": button,
                                    "frame_id": self.last_frame_id,
                                    "window": self.target.title,
                                },
                                f"Клик {button} в {position['position']}; "
                                "ближайший предыдущий кадр.",
                            )
                self.mouse_down = down
        except Exception:
            self.log.exception("MOUSE_SAMPLE_ERROR")
        finally:
            if not self.closed:
                self.root.after(20, self.poll_mouse)

    def add_note(self):
        self.reset_capture_evidence()
        self.decision_stream.reset()
        was_paused, self.paused = self.paused, True
        try:
            text = simpledialog.askstring(
                "Заметка к эпизоду", "Что произошло или прочиталось неверно?", parent=self.root
            )
            if text:
                self.recorder.event(
                    "note",
                    {"text": text, "frame_id": self.last_frame_id},
                    "Комментарий пользователя: " + text,
                )
        finally:
            self.paused = was_paused

    def draw(self):
        if not self.target or self.paused or not self.desktop.own_foreground(self.target.handle):
            return
        rect = self.desktop.rect(self.target.handle)
        if not rect:
            return
        x, y, width, height = rect
        if self.state.size and self.state.size != (width, height):
            self.hide()
            return
        signature = (
            rect,
            self.rois.get(),
            self.hand.to_dict(),
            self.hand_confirmed,
            int(time.monotonic() / 10),
            tuple(
                (
                    s.key,
                    s.name,
                    s.manual,
                    s.missing,
                    s.conflict,
                    tuple(s.observation.to_dict().items()),
                )
                for s in self.state.seats.values()
            ),
        )
        if signature == self.last_draw:
            return
        self.canvas.delete("all")
        if self.rois.get():
            self.layer.deiconify()
        else:
            self.layer.withdraw()
        self.desktop.position(self.layer, x, y, width, height)
        self.hand_label.configure(text=hand_text(self.hand, self.hand_confirmed))
        self.hand_panel.update_idletasks()
        info_height = self.hand_label.winfo_reqheight()
        self.hand_panel.deiconify()
        self.desktop.position(self.hand_panel, x + 12, y + 12, 395, info_height)
        for card in self.hand.cards:
            cx, cy, cw, ch = card.roi
            color = "#61cfff" if card.value and card.confidence >= 75 else "#ff6b74"
            self.canvas.create_rectangle(cx, cy, cx + cw, cy + ch, outline=color, width=2)
            self.canvas.create_text(cx, cy - 8, text=card.value or "?", fill=color, anchor="sw")
        for key in list(self.cards):
            if key not in self.state.seats:
                self.cards.pop(key).destroy()
            elif self.state.seats[key].missing:
                self.cards[key].withdraw()
        obstacles = [seat.observation.roi for seat in self.state.seats.values()]
        obstacles.append((12, 12, 395, info_height))
        obstacles.extend(card.roi for card in self.hand.cards)
        obstacles.extend(
            [
                (width * 0.35, height * 0.38, width * 0.3, height * 0.2),
                (width * 0.25, height * 0.87, width * 0.55, height * 0.13),
            ]
        )
        for seat in self.state.seats.values():
            px, py, pw, ph = seat.observation.roi
            if py > height * 0.75 and width * 0.35 < px < width * 0.65:
                obstacles.append((px - 10, py - ph * 1.8, pw + 20, ph * 1.8))
        for key, seat in self.state.seats.items():
            if seat.missing:
                continue
            px, py, pw, ph = seat.observation.roi
            color = name_color(seat)
            self.canvas.create_rectangle(px, py, px + pw, py + ph, outline=color, width=2)
            self.canvas.create_line(
                px, py + ph * 0.46, px + pw, py + ph * 0.46, fill=color, dash=(4, 3)
            )
            if key not in self.cards:
                card = tk.Toplevel(self.root)
                card.overrideredirect(True)
                card.attributes("-topmost", True)
                frame = tk.Frame(card, bg="#142130", highlightthickness=1)
                frame.pack(fill="both", expand=True)
                heading = tk.Label(
                    frame,
                    bg="#142130",
                    font=("Segoe UI", 10, "bold"),
                    padx=9,
                    pady=4,
                    justify="left",
                    wraplength=240,
                    cursor="hand2",
                )
                heading.pack(fill="x")
                label = tk.Label(
                    frame,
                    bg="#142130",
                    fg="#e8f2ff",
                    font=("Segoe UI", 9),
                    padx=9,
                    pady=5,
                    justify="left",
                    cursor="hand2",
                    wraplength=240,
                )
                label.pack(fill="both", expand=True)
                for widget in (label, heading):
                    widget.bind("<ButtonPress-1>", lambda e, k=key: self.start_drag(k, e))
                    widget.bind("<B1-Motion>", self.move_drag)
                    widget.bind("<ButtonRelease-1>", self.end_drag)
                    widget.bind("<Button-3>", lambda _, k=key: self.edit_player_note(k))
                card.label = label
                card.heading = heading
                card.frame = frame
                card.stats_key = None
                card.stats_text = ""
                self.cards[key] = card
                self.exclusion_ok &= self.desktop.configure_overlay(card)
                card.attributes("-alpha", 1 - self.ui_settings["transparency"] / 100)
            card = self.cards[key]
            identity = (
                seat.name,
                seat.conflict,
                self.player_store.revision,
                int(time.monotonic() / 10),
            )
            if card.stats_key != identity:
                card.stats_key = identity
                try:
                    if seat.name and not seat.conflict:
                        live = self.player_store.summary(seat.name)
                        card.stats_text = (
                            f"Совместно наблюдалось: {live['hands']} рук\n" + live["style"]
                        )
                        if live["note"]:
                            card.stats_text += "\nМоя заметка: " + live["note"]
                        if self.database:
                            archive = read_statistics(self.database, seat.name)
                            if archive:
                                card.stats_text += f"\nОтдельный архив: {archive['hands']} рук"
                    else:
                        card.stats_text = "Статистика: уточните никнейм"
                except Exception:
                    self.log.exception("STATISTICS_ERROR name=%s", seat.name)
                    card.stats_text = "Статистика: ошибка БД (см. лог)"
            source = "✓ вручную" if seat.manual else f"OCR {seat.observation.confidence:.0f}%"
            note = " · проверить смену игрока" if seat.conflict else ""
            visible_name = seat.name or "Подтверждаем никнейм…"
            card.heading.configure(text=f"{visible_name} · {source}{note}", fg=color)
            card.frame.configure(highlightbackground=color)
            card.label.configure(
                text=(
                    f"{stack_text(seat.observation.roi, self.live_evidence.previous)}"
                    f"\n{card.stats_text}"
                ),
            )
            card.update_idletasks()
            card_height = max(86, card.frame.winfo_reqheight())
            card_x, card_y, _, _ = place_card(
                seat.display_roi or seat.observation.roi,
                (width, height),
                (260, card_height),
                obstacles,
            )
            previous = getattr(card, "stable_box", None)
            if previous and previous[2:] == (260, card_height):
                bx, by, bw, bh = previous
                if (
                    0 <= bx <= width - bw
                    and 0 <= by <= height - bh
                    and not any(overlap(previous, obstacle) for obstacle in obstacles)
                ):
                    card_x, card_y = bx, by
            custom = self.ui_settings["positions"].get(self.panel_slot(seat))
            if custom:
                card_x, card_y = panel_position(custom, (width, height), (260, card_height))
            card.stable_box = (card_x, card_y, 260, card_height)
            obstacles.append(card.stable_box)
            card.deiconify()
            self.desktop.position(card, x + card_x, y + card_y, 260, card_height)
        self.last_draw = signature

    def panel_slot(self, seat):
        if self.monitor_slots:
            x, y = seat.observation.roi[:2]
            slot = min(
                self.monitor_slots, key=lambda s: (s["roi"][0] - x) ** 2 + (s["roi"][1] - y) ** 2
            )
            return str(slot["seat_index"])
        return f"temporary-{seat.key}"

    def change_hero_seat(self, _=None):
        self.hero_seat = self.hero_selection.current()
        self.ui_settings["hero_seat"] = self.hero_seat
        self.persist_ui()
        self.generation += 1
        self.reset_capture_evidence()
        self.hand = HandObservation()
        self.hand_tracker = HandTracker()
        self.hand_confirmed = False
        self.state = TableState(self.player_store.resolve_name)
        self.hide()
        self.names_meta = {}
        self.last_names = 0
        self.recorder.event(
            "hero_seat_changed",
            {"hero_seat": self.hero_seat},
            "Изменено место героя: " + self.hero_selection.get(),
        )

    def change_auto_size(self):
        self.ui_settings["auto_size_table"] = self.auto_size_table.get()
        self.persist_ui()

    def persist_ui(self):
        try:
            save_settings(self.settings_path, self.ui_settings)
        except OSError:
            self.log.exception("HUD_SETTINGS_WRITE_ERROR")
            self.status.set("Не удалось сохранить настройки HUD, см. лог")

    def change_transparency(self, value):
        value = min(80, max(0, float(value)))
        self.ui_settings["transparency"] = value
        self.transparency_text.set(f"Прозрачность: {value:.0f}%")
        for card in self.cards.values():
            card.attributes("-alpha", 1 - value / 100)
            self.exclusion_ok &= self.desktop.configure_overlay(card)

    def reset_positions(self):
        self.ui_settings["positions"] = {}
        for card in self.cards.values():
            card.stable_box = None
        self.persist_ui()
        self.last_draw = None
        self.draw()

    def start_drag(self, key, event):
        if key in self.cards:
            card = self.cards[key]
            self.drag = {
                "key": key,
                "start": (event.x_root, event.y_root),
                "origin": (card.winfo_rootx(), card.winfo_rooty()),
                "moved": False,
            }

    def move_drag(self, event):
        if not self.drag or not self.target:
            return
        key = self.drag["key"]
        rect = self.desktop.rect(self.target.handle)
        if not rect or key not in self.cards or key not in self.state.seats:
            return
        dx, dy = event.x_root - self.drag["start"][0], event.y_root - self.drag["start"][1]
        if abs(dx) + abs(dy) < 5 and not self.drag["moved"]:
            return
        self.drag["moved"] = True
        x, y, w, h = rect
        card = self.cards[key]
        cw, ch = 260, max(86, card.frame.winfo_reqheight())
        px = min(max(0, w - cw), max(0, self.drag["origin"][0] + dx - x))
        py = min(max(0, h - ch), max(0, self.drag["origin"][1] + dy - y))
        self.ui_settings["positions"][self.panel_slot(self.state.seats[key])] = [
            px / max(1, w - cw),
            py / max(1, h - ch),
        ]
        card.stable_box = (px, py, cw, ch)
        self.desktop.position(card, x + px, y + py, cw, ch)

    def end_drag(self, event):
        if not self.drag:
            return
        drag, self.drag = self.drag, None
        if drag["moved"]:
            self.persist_ui()
        else:
            self.edit(drag["key"])

    def update_monitor(self, context, meta):
        signals = context.get("table_signals", {})
        self.monitor_slots = signals.get("slots", [])
        identity = context.get("hand_id", {}).get("value", "?")
        street = context.get("decision_hand", {}).get("street", "?")
        labels = {}
        for slot in self.monitor_slots:
            action = slot.get("action_label")
            if not action:
                continue
            index = slot["seat_index"]
            marker = (identity, street, action["action"])
            labels[index] = marker
            if self.action_labels.get(index) != marker:
                accepted = self.recorder.event(
                    "player_action_observed",
                    {
                        **meta,
                        "seat_index": index,
                        "hand_id": identity,
                        "street": street,
                        "action": action["action"],
                        "evidence": action,
                        "verified_for_statistics": False,
                    },
                    f"Наблюдение: место {index + 1}, {action['text']}. "
                    "Записано в журнал; статистика действий ещё не начисляется.",
                )
                if accepted:
                    self.observed_actions += 1
                else:
                    labels.pop(index)
        self.action_labels = labels
        if self.paused or not self.target or not self.desktop.own_foreground(self.target.handle):
            self.monitor_status.set("Нейросеть выключена · наблюдение приостановлено")
            return
        dealer = signals.get("dealer_slot")
        description = f"место {dealer + 1}" if dealer is not None else "не определён"
        self.monitor_status.set(
            f"Нейросеть выключена · последний разбор кадра {meta.get('frame_id', '?')} · "
            f"дилер: {description}\nФрагментов действий в журнале: {self.observed_actions} · "
            "в БД пока только руки/заметки"
        )

    def show_odds(self):
        self.reset_capture_evidence()
        self.decision_stream.reset()
        paused, self.paused = self.paused, True
        try:
            if not self.hand_confirmed or not self.hand.odds:
                messagebox.showinfo("Шансы комбинаций", "Нужны два уверенных чтения карт подряд.")
                return
            odds = self.hand.odds
            lines = [
                f"{name}: {odds['probabilities'][str(rank)]:.2%}"
                for rank, name in CATEGORIES.items()
            ]
            method = "Полный перебор" if odds["method"] == "exact" else "Выборочная оценка"
            lines += [
                f"\nУсилить категорию к риверу: {odds['improvement_probability']:.2%}.",
                "Усиление — более старшая категория; улучшение кикера не учитывается.",
                f"\n{method}: {odds['runouts']} продолжений.",
                "Вероятность итоговой лучшей комбинации из семи карт.",
                "Это не шанс победы. Карты и диапазоны соперников не заданы.",
            ]
            messagebox.showinfo("Комбинация к риверу", "\n".join(lines))
        finally:
            self.paused = paused

    def edit(self, key):
        seat = self.state.seats.get(key)
        if seat is None:
            return
        self.reset_capture_evidence()
        self.decision_stream.reset()
        was_paused = self.paused
        self.paused = True
        try:
            name = simpledialog.askstring(
                "Никнейм игрока",
                "Введите точное имя. Пустая строка вернёт OCR.\n"
                "Точное имя сохраняется. Похожие OCR-опечатки объединяются со статистикой.",
                initialvalue=seat.name,
                parent=self.root,
            )
            if name is not None and key in self.state.seats:
                self.recorder.event(
                    "manual_name",
                    {
                        "frame_id": self.last_frame_id,
                        "seat": key,
                        "ocr_name": seat.observation.name,
                        "raw_name": seat.observation.raw_name,
                        "corrected_name": name,
                        "roi": seat.observation.roi,
                        "names_source": self.names_meta,
                    },
                    f"Исправлен ник: {seat.observation.raw_name!r} → {name!r}.",
                )
                old_name = seat.name or seat.observation.name
                self.state.correct(key, name)
                try:
                    if name.strip():
                        from difflib import SequenceMatcher

                        # Action labels must never become global aliases of a player.
                        similar = (
                            SequenceMatcher(
                                None, old_name.casefold(), name.strip().casefold()
                            ).ratio()
                            >= 0.7
                        )
                        self.player_store.correct_identity(
                            old_name if old_name and similar else name,
                            name,
                            {
                                "source": "manual_hud",
                                "old_name": old_name,
                                "metadata": self.names_meta,
                            },
                        )
                    self.stats_collector.correct_current(self.state)
                except Exception:
                    self.log.exception("PLAYER_IDENTITY_WRITE_ERROR")
                    self.stats_status.set("Статистика: исправление не сохранено (см. лог)")
                self.log.info(
                    "MANUAL_NAME seat=%s name=%s roi=%s",
                    key,
                    json.dumps(name, ensure_ascii=False),
                    seat.observation.roi,
                )
        finally:
            self.paused = was_paused
        self.draw()

    def edit_player_note(self, key):
        seat = self.state.seats.get(key)
        if not seat or not seat.name or seat.conflict:
            messagebox.showinfo("Стиль игрока", "Сначала уточните никнейм левой кнопкой мыши.")
            return
        name = seat.name
        self.reset_capture_evidence()
        self.decision_stream.reset()
        was_paused, self.paused = self.paused, True
        try:
            summary = self.player_store.summary(name)
            note = simpledialog.askstring(
                "Заметка об игроке: " + name,
                f"Совместно наблюдалось: {summary['hands']} рук.\n{summary['style']}\n"
                "Ваше описание поведения (пустая строка удаляет заметку):",
                initialvalue=summary["note"],
                parent=self.root,
            )
            if note is not None:
                self.player_store.set_note(name, note)
                self.recorder.event(
                    "player_note", {"name": name, "note": note}, f"Заметка об игроке {name}: {note}"
                )
        finally:
            self.paused = was_paused
        self.last_draw = None
        self.draw()

    def backup_statistics(self):
        from uuid import uuid4

        destination = (
            self.player_store.path.parent
            / "backups"
            / (f"players_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:6]}.sqlite3")
        )
        try:
            self.player_store.backup(destination)
            self.stats_status.set(f"Копия сохранена: {destination.name}")
            messagebox.showinfo(
                "Перенос статистики",
                f"Готовая копия базы:\n{destination}\n\n"
                "Этот файл можно перенести на другой компьютер.",
            )
        except Exception:
            self.log.exception("PLAYER_BACKUP_ERROR")
            self.stats_status.set("Ошибка резервной копии (см. лог)")

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.log.info("STOP")
        self.persist_ui()
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.names_pool.shutdown(wait=False, cancel_futures=True)
        self.fast_pool.shutdown(wait=False, cancel_futures=True)
        self.recorder.close()
        self.player_store.close()
        self.capture.close()
        self.root.destroy()

    def run(self):
        if not self.closed:
            self.root.mainloop()
