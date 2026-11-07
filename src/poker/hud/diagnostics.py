"""Bounded, asynchronous evidence recording. Observations are not game history."""

import hashlib
import json
import logging
import platform
import queue
import threading
import time
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from uuid import uuid4

import cv2


class Recorder:
    def __init__(self, root, image_limit=1024**3, queue_size=16):
        self.path = Path(root) / f"session_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:6]}"
        self.path.mkdir(parents=True)
        (self.path / "frames").mkdir()
        (self.path / "ocr_frames").mkdir()
        (self.path / "requests").mkdir()
        self.image_limit = image_limit
        self.image_bytes = 0
        self.dropped = 0
        self.error = ""
        self.limit_reached = False
        self.closed = False
        self.sequence = 0
        self.last_image = -float("inf")
        self.queue = queue.Queue(maxsize=queue_size)
        self.events = self._logger("events.jsonl", 8_000_000, 3)
        self.notes = self._logger("timeline.md", 4_000_000, 2)
        sources = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path(__file__).parent.iterdir()
            if p.suffix == ".py" or p.name == "rank_templates.json"
        }
        (self.path / "session.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "started_at": datetime.now(UTC).isoformat(),
                    "python": platform.python_version(),
                    "platform": platform.platform(),
                    "source_sha256": sources,
                    "image_limit_bytes": image_limit,
                    "nominal_capture_hz": 4,
                    "nominal_image_hz": 2,
                    "text_ocr_lossless_frames": True,
                    "fast_table_lossless_frames": True,
                    "decision_source": "fast_table",
                    "nominal_fast_turn_hz": 4,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (self.path / "README.md").write_text(
            "# Диагностика HUD\n\nНачните с timeline.md — это хронология на русском.\n"
            "events.jsonl содержит по одному событию JSON в строке; frame_id связывает "
            "кадр, OCR, карты и клики. captured_at — время кадра, at — время события.\n"
            "frames/*.jpg — исходные кадры стола без HUD, до двух в секунду.\n"
            "ocr_frames/*.png — точные кадры текстового OCR и быстрого разбора стола; "
            "путь записан в lossless_image события frame. PNG входят в общий лимит.\n"
            "У события кадра image=null, если изображение не сохранено.\n"
            "Координаты ROI и кликов — пиксели клиентской области; norm — доли её размера.\n"
            "События cards и names имеют независимые времена: текст обновляется медленнее.\n"
            "requests/*.draft.json — пробные запросы в моменты своего хода; null означает "
            "неизвестное поле. Они не отправляются в нейросеть. Рядом лежат точный PNG "
            "и *.evidence.json с причинами блокировки, OCR и временем исходного кадра. "
            "Номер файла — frame_id. До 1000 комплектов на сеанс; "
            "PNG входят в общий лимит изображений.\n"
            "window — метка выбранного окна; её номер раздачи может устареть. "
            "window_title_capture содержит текущий заголовок до/после кадра. "
            "table_stakes хранит лимиты и два источника подтверждения; "
            "старый заголовок без чтений при захвате остаётся кандидатом. "
            "Режим взрывного банка в заголовке не определяет тип текущей раздачи.\n"
            "Запросы формируются быстрым потоком независимо от OCR имён; "
            "decision_source=fast_table. Пустое имя допустимо, место игрока сохраняется. "
            "Банк, баттон и стеки читаются с того же кадра. stage_ms показывает "
            "время этапов; параллельные этапы нельзя складывать как общую задержку.\n"
            "requests/*.advisor.json — новый диагностический контракт с фрагментами "
            "истории и подтверждёнными состояниями игроков. history_complete=false "
            "означает неполную историю; model_called=false — сеть не вызывалась.\n"
            "Клики и OCR не доказывают выполненное действие или принятую ставку. "
            "Сырые суммы и кандидат баттона требуют проверки по изображению.\n"
            "При потере фокуса и на паузе захват останавливается. "
            "Опрос мыши может пропустить очень короткий клик; клавиатура не записывается.\n"
            "JPEG может изменить тонкие детали. Для точного PNG используйте «Снимок».\n"
            "Изображения ограничены 1 ГиБ на запуск, старые сеансы не удаляются. "
            "Текстовые журналы ротируются: events.jsonl до 32 МБ, timeline.md до 12 МБ. "
            "Файлы .1, .2, .3 — предыдущие части (больший номер старше).\n"
            "Лимиты, сбои записи и потерянные задания отображаются в HUD.\n"
            "Свои пояснения можно добавлять кнопкой «Заметка» либо в comments.md.\n",
            encoding="utf-8",
        )
        (self.path / "comments.md").write_text("# Мои комментарии\n\n", encoding="utf-8")
        self.worker = threading.Thread(target=self._run, name="hud-recorder", daemon=True)
        self.worker.start()
        self.event("start", {}, "Запись диагностики началась.")

    def _logger(self, name, size, backups):
        logger = logging.getLogger(str(self.path / name))
        logger.setLevel(logging.INFO)
        logger.propagate = False
        handler = RotatingFileHandler(
            self.path / name, maxBytes=size, backupCount=backups, encoding="utf-8"
        )

        # Logging normally swallows disk failures; expose them to the HUD.
        def failed(_):
            self.error = f"Не удалось записать {name}"

        handler.handleError = failed
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        return logger

    def event(self, kind, data, comment="", frame=None):
        if self.closed:
            return False
        item = {"schema_version": 1, "at": datetime.now(UTC).isoformat(), "kind": kind, **data}
        try:
            self.queue.put_nowait((item, comment, frame))
            return True
        except queue.Full:
            self.dropped += 1
            return False

    def frame(self, frame, metadata, force_image=False, *, lossless=False):
        self.sequence += 1
        frame_id = self.sequence
        now = time.monotonic()
        image = None
        if (
            (force_image or lossless or now - self.last_image >= 0.5)
            and not self.limit_reached
            and not self.error
        ):
            image = frame.copy()
            self.last_image = now
        self.event(
            "frame", {**metadata, "frame_id": frame_id, "lossless_requested": lossless}, frame=image
        )
        return frame_id

    def status(self):
        if self.error:
            return "Запись: ОШИБКА (см. лог)"
        if self.limit_reached:
            return "Запись: лимит кадров, текст продолжается"
        return f"Запись: {self.image_bytes / 1024**2:.0f} МБ · пропусков {self.dropped}"

    def _run(self):
        while True:
            task = self.queue.get()
            try:
                if task is None:
                    return
                item, comment, frame = task
                if item["kind"] in {"frame", "decision_dry_run"}:
                    item["image"] = None
                    if frame is not None:
                        decision = item["kind"] == "decision_dry_run"
                        extension = ".png" if decision else ".jpg"
                        ok, encoded = cv2.imencode(
                            extension, frame, [] if decision else [cv2.IMWRITE_JPEG_QUALITY, 90]
                        )
                        if not ok:
                            raise OSError("JPEG encoding failed")
                        if self.image_bytes + encoded.nbytes <= self.image_limit:
                            folder = "requests" if decision else "frames"
                            name = f"{folder}/{item['frame_id']:08d}{extension}"
                            encoded.tofile(self.path / name)
                            self.image_bytes += encoded.nbytes
                            item["image"] = name
                        else:
                            self.limit_reached = True
                            comment = "Достигнут лимит изображений. Текстовая запись продолжается."
                        if not decision and item.get("lossless_requested"):
                            item["lossless_image"] = None
                            ok, lossless = cv2.imencode(".png", frame)
                            if not ok:
                                raise OSError("Cannot encode lossless OCR frame")
                            if self.image_bytes + lossless.nbytes <= self.image_limit:
                                name = f"ocr_frames/{item['frame_id']:08d}.png"
                                lossless.tofile(self.path / name)
                                self.image_bytes += lossless.nbytes
                                item["lossless_image"] = name
                            else:
                                self.limit_reached = True
                                comment = (
                                    "Достигнут лимит изображений. Текстовая запись продолжается."
                                )
                if item["kind"] == "decision_dry_run":
                    # Bound standalone request artifacts as well as the rotating logs.
                    request_number = getattr(self, "request_count", 0)
                    if request_number < 1000:
                        self.request_count = request_number + 1
                        suffix = "request" if item["would_send"] else "draft"
                        base = self.path / "requests" / f"{item['frame_id']:08d}"
                        base.with_suffix(f".{suffix}.json").write_text(
                            json.dumps(item["request"], ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                        base.with_suffix(".evidence.json").write_text(
                            json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8"
                        )
                        if item.get("advisor") is not None:
                            base.with_suffix(".advisor.json").write_text(
                                json.dumps(item["advisor"], ensure_ascii=False, indent=2),
                                encoding="utf-8",
                            )
                    else:
                        item["artifact_limit_reached"] = True
                item["dropped_jobs"] = self.dropped
                self.events.info(json.dumps(item, ensure_ascii=False))
                if comment:
                    comment = comment.replace("\r", " ").replace("\n", " ")
                    frame_ref = f" · кадр {item['frame_id']}" if "frame_id" in item else ""
                    self.notes.info(f"- {item['at']}{frame_ref} — {comment}")
            except Exception as error:
                self.error = str(error)
            finally:
                self.queue.task_done()

    def close(self):
        if self.closed:
            return
        self.event("stop", {"dropped_jobs": self.dropped}, "Запись завершена.")
        self.closed = True
        try:
            self.queue.put(None, timeout=5)
        except queue.Full:
            self.error = "Не удалось завершить очередь записи"
            return
        self.worker.join(timeout=10)
        if self.worker.is_alive():
            self.error = "Не удалось завершить запись за 10 секунд"
            return
        for logger in (self.events, self.notes):
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)
