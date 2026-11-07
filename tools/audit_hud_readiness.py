"""Compare recorded HUD sessions without OCR, inference, training or database access."""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median

from poker.hud.session_images import saved_frame_path

# These are explicit restrictions of the current producer, not measured OCR errors.
# Keep unknown reasons: adding a new blocker must never silently improve this report.
FIXED_GATES = {
    "table_membership_unverified",
    "betting_state_unverified",
    "stacks_unverified",
    "turn_continuity_unverified",
    "hud_state_reconstruction_unverified",
}
UNIMPLEMENTED_FIELDS = {
    "big_blind_unknown_or_invalid",
    "seat_order_unverified",
    "history_incomplete",
}


def blocker_group(reason):
    if reason in FIXED_GATES:
        return "producer_gates"
    if reason in UNIMPLEMENTED_FIELDS or (
        reason.startswith("player.") and reason.endswith(".hand_contribution_unknown_or_invalid")
    ):
        return "unimplemented_contract_fields"
    return "observation_or_other"


def read_events(session):
    files = sorted(session.glob("events.jsonl*"))
    if not files:
        raise ValueError(f"No event logs in {session}")
    events, hashes = [], {}
    for path in files:
        data = path.read_bytes()
        hashes[path.name] = hashlib.sha256(data).hexdigest()
        for number, line in enumerate(data.decode("utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                datetime.fromisoformat(row["at"])
                if not isinstance(row["kind"], str):
                    raise ValueError("kind must be text")
            except (ValueError, TypeError, KeyError) as error:
                raise ValueError(f"{path}:{number}: {error}") from error
            events.append(row)
    # Rotated logs overlap in time. Preserve file order for ties; do not deduplicate
    # identical events silently: they can themselves be evidence of recorder defects.
    return sorted(events, key=lambda r: datetime.fromisoformat(r["at"])), hashes


def distribution(values):
    values = sorted(values)
    return (
        {
            "count": len(values),
            "median": median(values),
            "p95": values[int(0.95 * (len(values) - 1))],
            "maximum": values[-1],
        }
        if values
        else {"count": 0, "median": None, "p95": None, "maximum": None}
    )


def turn_windows(events):
    """Measured card-stream intervals, not inferred game decisions or complete hands."""
    windows, current = [], None
    cards = sorted((r for r in events if r["kind"] == "cards"), key=lambda r: r["captured_at"])

    def key(row):
        return (
            row.get("window"),
            tuple(row.get("client_rect", [])),
            row.get("evidence_epoch"),
            row.get("hero_seat"),
        )

    for row in cards:
        hand = row["hand"]
        if hand.get("my_turn") is not True:
            current = None
            continue
        state = key(row), hand.get("hero", []), hand.get("board", [])
        at = datetime.fromisoformat(row["captured_at"])
        if (
            current is None
            or current["state"] != state
            or (at - datetime.fromisoformat(current["last_capture"])).total_seconds() > 5
        ):
            current = {
                "state": state,
                "first_capture": row["captured_at"],
                "first_frame_id": row["frame_id"],
                "last_capture": row["captured_at"],
                "last_frame_id": row["frame_id"],
                "draft_frames": [],
                "timely_draft_frames": [],
            }
            windows.append(current)
        current["last_capture"], current["last_frame_id"] = row["captured_at"], row["frame_id"]
    for window in windows:
        first, last = (datetime.fromisoformat(window[k]) for k in ("first_capture", "last_capture"))
        for row in events:
            if row["kind"] != "decision_dry_run":
                continue
            request = row.get("request", {})
            state = key(row), request.get("hero_hole_cards", []), request.get("board_cards", [])
            if (
                state != window["state"]
                or not first <= datetime.fromisoformat(row["captured_at"]) <= last
            ):
                continue
            window["draft_frames"].append(row["frame_id"])
            if datetime.fromisoformat(row["at"]) <= last:
                window["timely_draft_frames"].append(row["frame_id"])
        window["duration_seconds"] = (last - first).total_seconds()
        del window["state"]
    return windows


def summarize(session):
    events, hashes = read_events(session)
    counts = Counter(row["kind"] for row in events)
    latency = {}
    for kind in ("cards", "fast_table", "names", "decision_dry_run"):
        latency[kind] = distribution(
            (
                datetime.fromisoformat(row["at"]) - datetime.fromisoformat(row["captured_at"])
            ).total_seconds()
            for row in events
            if row["kind"] == kind
        )
    turns = [r for r in events if r["kind"] == "cards" and r["hand"].get("my_turn") is True]
    drafts = [r for r in events if r["kind"] == "decision_dry_run"]
    reasons, grouped, fields = Counter(), defaultdict(Counter), defaultdict(Counter)
    missing_advisor, clear = 0, 0
    for row in drafts:
        advisor = row.get("advisor")
        if not isinstance(advisor, dict) or not isinstance(advisor.get("blockers"), list):
            missing_advisor += 1
            continue
        blockers = set(advisor["blockers"])
        reasons.update(blockers)
        for reason in blockers:
            grouped[blocker_group(reason)][reason] += 1
        observation = advisor.get("observation")
        if not isinstance(observation, dict):
            continue
        clear += not blockers
        for key in ("big_blind", "clockwise_seats", "pot", "dealer_seat", "history_complete"):
            value = observation.get(key)
            known = value is True if key == "history_complete" else value is not None
            fields[key]["present" if known else "missing"] += 1
        for player in observation.get("players", []):
            for key in (
                "stack",
                "street_contribution",
                "hand_contribution",
                "cards_dealt",
                "folded",
                "all_in",
            ):
                fields["players." + key][
                    "present" if player.get(key) is not None else "missing"
                ] += 1
    rejections = Counter(
        reading["rejection"]
        for row in events
        if row["kind"] == "names"
        for reading in row.get("context", {}).get("stack_readings", {}).values()
        if reading.get("rejection")
    )
    return {
        "schema_version": "hud-readiness-audit/1",
        "session": str(session.resolve()),
        "input_sha256": hashes,
        "event_counts": dict(counts),
        "latency_seconds": latency,
        "hero_seats": dict(Counter(str(r.get("hero_seat", "not_recorded")) for r in turns)),
        "observed_turn_windows": turn_windows(events),
        "turn_cards": {
            "observations": len(turns),
            "reported_valid": sum(r["hand"].get("valid") is True for r in turns),
            "with_odds": sum(r["hand"].get("odds") is not None for r in turns),
            "exact_images": sum(saved_frame_path(session, r["frame_id"]).is_file() for r in turns),
            "invalid_frame_ids": [r["frame_id"] for r in turns if not r["hand"].get("valid")],
            "accuracy_measured": False,
        },
        "drafts": {
            "count": len(drafts),
            "missing_advisor_diagnostics": missing_advisor,
            "without_recorded_blockers": clear,
            "blockers": dict(reasons),
            "blocker_groups": {k: dict(v) for k, v in grouped.items()},
            "field_presence": {k: dict(v) for k, v in fields.items()},
        },
        "stack_rejections": dict(rejections),
        "notes": [r for r in events if r["kind"] == "note"],
        "manual_names": [r for r in events if r["kind"] == "manual_name"],
        "maximum_dropped_jobs": max((r.get("dropped_jobs", 0) for r in events), default=0),
        "model_called": False,
        "player_db_written": False,
    }


def render(reports):
    lines = [
        "# Состояние записанных сессий HUD",
        "",
        "Это аудит сохранённых событий, без повторного OCR. Версии кода сессий могут отличаться.",
        "Валидность карт и наличие полей — внутренние проверки, не измеренная точность.",
        "Количество черновиков не равно числу решений игрока. Нулевой пропуск очереди не означает",
        "полноту записи всех кадров. Нейросеть, обучение и БД не используются.",
        "",
        "| Сессия | Карты прошли проверку / кадры хода | Точные снимки | Черновики "
        "| Без блокировок | OCR текста p95, с |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for report in reports:
        cards, drafts = report["turn_cards"], report["drafts"]
        p95 = report["latency_seconds"]["names"]["p95"]
        latency_label = f"{p95:.3f}" if p95 is not None else "—"
        lines.append(
            f"| {Path(report['session']).name} | {cards['reported_valid']}/{cards['observations']} "
            f"| {cards['exact_images']} | {drafts['count']} "
            f"| {drafts['without_recorded_blockers']} | {latency_label} |"
        )
    for report in reports:
        lines.extend(["", f"## {Path(report['session']).name}", ""])
        windows = report["observed_turn_windows"]
        covered = sum(bool(w["draft_frames"]) for w in windows)
        timely = sum(bool(w["timely_draft_frames"]) for w in windows)
        lines.extend(
            [
                f"Отрезков видимого хода с неизменными картами: {len(windows)}. "
                f"Черновик с кадра внутри отрезка есть у {covered}; "
                "успел сформироваться до последнего кадра отрезка у "
                f"{timely}.",
                "Это консервативное измерение задержки, не число настоящих решений: отсчёт идёт",
                "от первого до последнего наблюдения кнопок; смена карт, эпохи, геометрии или",
                "пауза более 5 секунд начинает новый отрезок. "
                "Отдельный кадр имеет нулевую длительность.",
                "",
            ]
        )
        for group, label in (
            ("producer_gates", "Постоянные запреты текущего источника"),
            ("unimplemented_contract_fields", "Поля, которые HUD пока не формирует полностью"),
            ("observation_or_other", "Причины в наблюдениях и прочие ограничения"),
        ):
            lines.extend([f"### {label}", ""])
            for reason, count in sorted(report["drafts"]["blocker_groups"].get(group, {}).items()):
                lines.append(f"- `{reason}`: {count} черновиков.")
        lines.extend(
            [
                "",
                "Разделение причин описывает текущую реализацию. Оно не разрешает отправку",
                "и не доказывает, что нужные значения невозможно извлечь из кадров.",
                "",
                "### Комментарии пользователя",
                "",
            ]
        )
        lines.extend(f"- Кадр {r.get('frame_id')}: {r['text']}" for r in report["notes"])
        if not report["notes"]:
            lines.append("Комментариев в JSONL нет.")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sessions", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Choose an empty output directory; existing audits are preserved")
    reports = [summarize(session) for session in args.sessions]
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "readiness.json").write_text(
        json.dumps({"sessions": reports}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output / "readiness.md").write_text(render(reports), encoding="utf-8")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
