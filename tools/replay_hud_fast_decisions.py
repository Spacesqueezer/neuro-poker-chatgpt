"""Replay exact saved fast captures with a serial-worker timing model; never run a policy."""

import argparse
import hashlib
import json
from bisect import bisect_right
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter

import cv2

from poker.hud.bet_bridge import BetBridge
from poker.hud.decision_observer import fast_decision_draft
from poker.hud.decision_stream import DecisionStream
from poker.hud.fast_table import analyze_fast_table
from poker.hud.live_evidence import LiveEvidence
from poker.hud.recognition import configure_ocr
from poker.hud.session_images import saved_frame_path

if __package__:
    from .audit_hud_readiness import distribution, read_events, turn_windows
else:
    from audit_hud_readiness import distribution, read_events, turn_windows


def dt(value):
    return datetime.fromisoformat(value)


def coverage(cards, drafts):
    windows = turn_windows(cards + drafts)
    return {
        "windows": len(windows),
        "with_source_inside": sum(bool(w["draft_frames"]) for w in windows),
        "completed_inside": sum(bool(w["timely_draft_frames"]) for w in windows),
        "details": windows,
    }


def replay(session, output, *, max_frames=None):
    if output.exists() and any(output.iterdir()):
        raise ValueError("Choose an empty output directory; existing audits are preserved")
    events, hashes = read_events(session)
    frames = sorted(
        (r for r in events if r["kind"] == "fast_table"), key=lambda r: r["captured_at"]
    )
    cards = [dict(r, hero_seat=r.get("hero_seat", 6)) for r in events if r["kind"] == "cards"]
    card_times = [dt(r["at"]) for r in cards]
    boundaries = [
        dt(r["at"])
        for r in events
        if r["kind"]
        in (
            "window",
            "target",
            "pause",
            "hero_seat_changed",
        )
    ]
    original_drafts = [
        dict(r, hero_seat=r.get("hero_seat", 6)) for r in events if r["kind"] == "decision_dry_run"
    ]
    output.mkdir(parents=True, exist_ok=True)
    configure_ocr()
    live, stream, bridge = LiveEvidence(), DecisionStream(), BetBridge()
    drafts, counts, elapsed, turn_elapsed = [], Counter(), [], []
    busy_until = previous_capture = None
    with (output / "observations.jsonl").open("w", encoding="utf-8") as log:
        for row in frames[:max_frames]:
            captured = dt(row["captured_at"])
            if busy_until is not None and captured < busy_until:
                counts["skipped_worker_busy"] += 1
                continue
            epoch = row.get("evidence_epoch")
            if live.epoch != epoch or (
                previous_capture is not None
                and bisect_right(boundaries, previous_capture) != bisect_right(boundaries, captured)
            ):
                live, bridge = LiveEvidence(), BetBridge()
                live.epoch = epoch
                stream.reset()
            previous_capture = captured
            path = saved_frame_path(session, row["frame_id"])
            if not path.is_file():
                counts["missing_exact_image"] += 1
                live.reset()
                stream.reset()
                bridge = BetBridge()
                continue
            frame = cv2.imread(str(path))
            if frame is None:
                raise ValueError(f"Cannot read {path}")
            source = {
                k: row.get(k)
                for k in (
                    "frame_id",
                    "captured_at",
                    "window",
                    "window_handle",
                    "window_title_capture",
                    "client_rect",
                    "evidence_epoch",
                )
            }
            source.update(hero_seat=row.get("hero_seat", 6), image=str(path.resolve()))
            start = perf_counter()
            context = analyze_fast_table(frame, source["hero_seat"])
            seconds = perf_counter() - start
            ready = captured + timedelta(seconds=seconds)
            elapsed.append(seconds)
            if context.get("decision_hand", {}).get("my_turn"):
                turn_elapsed.append(seconds)
            interrupted = bisect_right(boundaries, captured) != bisect_right(boundaries, ready)
            facts = None if interrupted else live.update(context, source, now=ready)
            draft = None
            if facts is None:
                counts["rejected"] += 1
                live.reset()
                stream.reset()
                bridge = BetBridge()
            else:
                facts = bridge.augment(source, context, facts)
                bridge.add(source, context, facts)
                index = bisect_right(card_times, ready)
                latest = cards[index - 1] if index else None
                draft = fast_decision_draft(
                    context,
                    source,
                    facts,
                    live.tracker,
                    stream,
                    latest_cards=latest,
                    now=ready,
                )
            # Include confirmation/build overhead, but not offline JSON/image I/O.
            ready = captured + timedelta(seconds=perf_counter() - start)
            busy_until = ready
            observation = {
                **source,
                "kind": "fast_table",
                "at": ready.isoformat(),
                "context": context,
                "accepted": facts is not None,
                "evidence": facts,
                "model_called": False,
                "image_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "offline_read_seconds": seconds,
                "replay": True,
            }
            log.write(json.dumps(observation, ensure_ascii=False) + "\n")
            if draft:
                drafts.append(
                    {**draft, "kind": "decision_dry_run", "at": ready.isoformat(), "replay": True}
                )
            counts["processed"] += 1
            if counts["processed"] % 50 == 0:
                print(
                    f"{session.name}: {counts['processed']} frames, {len(drafts)} drafts",
                    flush=True,
                )
    with (output / "drafts.jsonl").open("w", encoding="utf-8") as log:
        for draft in drafts:
            log.write(json.dumps(draft, ensure_ascii=False) + "\n")
    fields = Counter()
    for draft in drafts:
        request = draft["request"]
        for key in ("total_pot", "call_amount_needed", "min_raise_amount", "max_raise_amount"):
            fields[key] += request.get(key) is not None
        fields["dealer"] += sum(p["is_dealer"] is True for p in request["players"]) == 1
        fields["player_rows"] += len(request["players"])
        fields["known_stacks"] += sum(p["stack"] is not None for p in request["players"])
        fields["known_street_bets"] += sum(p["current_bet"] is not None for p in request["players"])
    summary = {
        "schema_version": "fast-decision-replay/1",
        "session": str(session.resolve()),
        "input_sha256": hashes,
        "source_sha256": {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [Path(__file__), *Path("src/poker/hud").glob("*.py")]
        },
        "timing_model": "single_worker_on_recorded_fast_captures_without_concurrent_slow_OCR",
        "recorded_epochs_preserved": True,
        "partial": max_frames is not None,
        "recorded_fast_frames": len(frames),
        "counts": dict(counts),
        "read_seconds": distribution(elapsed),
        "turn_read_seconds": distribution(turn_elapsed),
        "drafts": len(drafts),
        "draft_field_presence": dict(fields),
        "without_blockers": sum(not r["blockers"] for r in drafts),
        "original_coverage": coverage(cards, original_drafts),
        "replay_coverage": coverage(cards, drafts),
        "model_called": False,
        "training_run": False,
        "player_db_written": False,
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    old, new = summary["original_coverage"], summary["replay_coverage"]
    (output / "review.md").write_text(
        "# Офлайн-проверка быстрого источника запросов\n\n"
        f"Источник: {session.name}. Обработано {counts['processed']} кадров; "
        f"черновиков {len(drafts)}.\n\n"
        f"Отрезков хода: {old['windows']}. Черновик успел появиться внутри отрезка: "
        f"в записи {old['completed_inside']}, в модели времени {new['completed_inside']}.\n\n"
        "Это не измерение нового HUD в живой игре. Использованы сохранённые моменты запуска "
        "быстрого обработчика и эпохи, включая прежние сбросы из-за медленного OCR. "
        "Занятый обработчик пропускает захваты. Новая частота 4 Гц не моделируется; "
        "конкурирующие потоки имён и карт не запущены. Задержка измерена на этой машине, "
        "чтение файла и запись отчёта в неё не входят. Из исходного карточного потока "
        "используются только результаты, уже доступные к модельному времени готовности.\n\n"
        "Поля могут оставаться неизвестными; наличие черновика не означает готовность к сети. "
        "Ручные исправления и будущие значения в запросы не подмешиваются. "
        "Исходники и снимки перечислены с хешами, исходная сессия и БД не изменяются.\n",
        encoding="utf-8",
    )
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-frames", type=int)
    args = parser.parse_args()
    if args.max_frames is not None and args.max_frames <= 0:
        parser.error("--max-frames must be positive")
    summary = replay(args.session, args.output, max_frames=args.max_frames)
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "counts",
                    "read_seconds",
                    "turn_read_seconds",
                    "drafts",
                    "without_blockers",
                )
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
