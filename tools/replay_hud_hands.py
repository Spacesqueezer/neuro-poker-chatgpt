"""Build auditable hand fragments from saved sessions; no model or player DB writes."""

import argparse
import hashlib
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path

import cv2

from poker.hud.bet_associations import associate_bets
from poker.hud.blind_audit import audit_blinds
from poker.hud.card_backs import card_back_pair
from poker.hud.cards import find_cards
from poker.hud.client_id import read_hand_id
from poker.hud.hand import observe
from poker.hud.hand_reconstruction import HandReconstructor
from poker.hud.recognition import configure_ocr, layout_panels
from poker.hud.session_images import frame_candidates, saved_frame_path
from poker.hud.table_signals import (
    read_action_label,
    read_bets,
    read_blind_label,
    read_settlement_label,
    recover_amount,
)


def rows(session, dense=False):
    selected = []
    names, cards = {}, {}
    for path in session.glob("events.jsonl*"):
        with path.open(encoding="utf8") as stream:
            for line in stream:
                if line.strip():
                    row = json.loads(line)
                    if dense and row["kind"] == "names":
                        names[row["frame_id"]] = row
                    if dense and row["kind"] == "cards":
                        cards[row["frame_id"]] = row["hand"]
                    if row["kind"] in {"frame" if dense else "names", "target", "window", "pause"}:
                        selected.append(row)
    if dense:
        for row in selected:
            if row["kind"] == "frame":
                text = names.get(row["frame_id"], {})
                row.update(
                    context=text.get("context", {}),
                    players=text.get("players", []),
                    card_observation=cards.get(row["frame_id"]),
                    text_sampled=bool(text),
                )
    return sorted(selected, key=lambda row: row["at"])


def cached_rows(session, cache):
    """Keep original capture boundaries when refreshing cached image observations."""
    cached = {}
    for line in cache.read_text(encoding="utf8").splitlines():
        row = json.loads(line)
        row["players"] = row.get("players") or []
        expected = {p.resolve() for p in frame_candidates(session, row["frame_id"])}
        if row.get("image") and Path(row["image"]).resolve() not in expected:
            raise ValueError("Cached observations belong to a different session")
        if row["frame_id"] in cached:
            raise ValueError("Duplicate cached frame")
        cached[row["frame_id"]] = row
    selected = []
    for original in rows(session, True):
        if original["kind"] != "frame":
            selected.append(original)
        elif original["frame_id"] in cached:
            row = cached.pop(original["frame_id"])
            for key in ("captured_at", "window", "client_rect"):
                if key in original and row.get(key) != original[key]:
                    raise ValueError(f"Cached {key} differs from source frame")
            row.update(kind="frame", at=original["at"])
            selected.append(row)
    if cached:
        raise ValueError("Cached frames are missing from source session events")
    return selected


def replay_observation(row, context, signals, image):
    """Keep cached numeric evidence and source epochs during label-only refresh."""
    result = {
        key: row.get(key)
        for key in ("frame_id", "captured_at", "window", "client_rect", "evidence_epoch")
    }
    result.update(
        players=row.get("players") or [],
        image=image,
        context={**context, "table_signals": signals},
    )
    return json.loads(json.dumps(result, ensure_ascii=False))


def replay(session, output, dense=False, cache=None, refresh_cards=False, recover_amounts=False):
    output.mkdir()
    tracker = HandReconstructor()
    counts = Counter()
    baseline = HandReconstructor() if cache else None
    with (output / "observations.jsonl").open("w", encoding="utf8") as observations:
        for row in cached_rows(session, cache) if cache else rows(session, dense):
            if row["kind"] not in {"names", "frame"}:
                tracker.interrupt("capture_boundary")
                if baseline is not None:
                    baseline.interrupt("capture_boundary")
                continue
            if dense and not (saved_frame_path(session, row["frame_id"])).exists():
                counts["unsaved_frames"] += 1
                continue
            counts["label_frames" if cache else "numeric_frames" if dense else "name_frames"] += 1
            if baseline is not None:
                baseline.update(row)
            context = row.get("context", {})
            signals = context.get("table_signals", {})
            path = saved_frame_path(session, row["frame_id"])
            image = cv2.imread(str(path)) if path.exists() else None
            if image is None:
                counts["missing_images"] += 1
            elif cache:
                counts["images"] += 1
                if refresh_cards:
                    hand = observe(find_cards(image)).to_dict()
                    context = {
                        **context,
                        "decision_hand": hand,
                        "hero_visible": len(hand["hero"]) == 2,
                    }
                for slot in signals.get("slots", []):
                    if recover_amounts:
                        bet = recover_amount(image, slot.get("bet_evidence", {}))
                        slot["bet_evidence"] = bet
                        slot["current_bet"] = bet.get("value")
                    slot["action_label"] = read_action_label(image, slot["roi"])
                    slot["action_sampled"] = True
                    slot["blind_label"] = read_blind_label(image, slot["roi"])
                    settlement = read_settlement_label(image, slot["roi"])
                    slot["settlement_label"] = settlement
                    if settlement:
                        slot["payout_evidence"] = slot.get("bet_evidence")
                        slot["current_bet"] = None
                if counts["images"] % 100 == 0:
                    print(f"{session.name}: {counts['images']} label frames", flush=True)
            else:
                counts["images"] += 1
                if dense:
                    # The frame id must match exactly; never carry cards or a hand id forward.
                    hand = row.get("card_observation")
                    if hand is None:
                        hand = observe(find_cards(image)).to_dict()
                        counts["card_fallback_frames"] += 1
                    context = {
                        **context,
                        "hand_id": read_hand_id(image),
                        "decision_hand": hand,
                        "hero_visible": len(hand.get("hero", [])) == 2,
                    }
                old = {s["seat_index"]: s for s in signals.get("slots", [])}
                slots = []
                rois = layout_panels(image)
                bets = read_bets(image, rois) if dense else []
                for index, roi in enumerate(rois):
                    previous = old.get(index, {})
                    aligned = (
                        len(old) == 7
                        and "roi" in previous
                        and math.dist(previous["roi"][:2], roi[:2]) < roi[2] * 0.15
                    )
                    slot = dict(previous) if aligned else {}
                    slot.update(
                        seat_index=index, roi=roi, card_back_evidence=card_back_pair(image, roi)
                    )
                    if dense:
                        slot.update(
                            current_bet=bets[index]["value"],
                            bet_evidence=bets[index],
                            action_sampled=row.get("text_sampled", False) and aligned,
                        )
                    slots.append(slot)
                    counts["card_back_pairs"] += slot["card_back_evidence"]["present"] is True
                    if previous and not aligned:
                        counts["discarded_misaligned_slots"] += 1
                signals = {**signals, "slots": slots}
                if dense:
                    signals["pot_sampled"] = row.get("text_sampled", False)
                if dense and counts["images"] % 100 == 0:
                    print(f"{session.name}: {counts['images']} numeric frames", flush=True)
            row = replay_observation(
                row, context, signals, str(path.resolve()) if image is not None else None
            )
            observations.write(json.dumps(row, ensure_ascii=False) + "\n")
            tracker.update(row)
    hands = list(tracker.hands.values())
    links = associate_bets(hands)
    observed = [
        json.loads(line)
        for line in (output / "observations.jsonl").read_text(encoding="utf8").splitlines()
    ]
    blind_checks = audit_blinds(hands, observed)
    with (output / "blind_amounts.jsonl").open("w", encoding="utf8") as stream:
        for check in blind_checks:
            stream.write(json.dumps(check, ensure_ascii=False) + "\n")
    with (output / "bet_action_links.jsonl").open("w", encoding="utf8") as stream:
        for link in links:
            stream.write(json.dumps(link, ensure_ascii=False) + "\n")
    counts["hand_fragments"] = len(hands)
    counts["unassigned_frames"] = tracker.skipped
    counts["participants_with_evidence"] = sum(len(h["participants"]) for h in hands)
    event_counts = Counter(e["kind"] for h in hands for e in h["events"])
    actions = Counter(
        e["action"] for h in hands for e in h["events"] if e["kind"] == "action_label"
    )
    summary = {
        "session": session.name,
        "input_mode": "dense_labels" if cache else "dense_bets" if dense else "name_frames",
        **counts,
        "events": dict(event_counts),
        "action_labels": dict(actions),
        "history_complete": False,
        "blind_amounts": dict(Counter(x["status"] for x in blind_checks)),
        "bet_action_links": dict(Counter(link["status"] for link in links)),
    }
    if baseline is not None:
        original_hands = list(baseline.hands.values())
        summary["cached_baseline"] = {
            "events": dict(Counter(e["kind"] for h in original_hands for e in h["events"])),
            "bet_action_links": dict(Counter(x["status"] for x in associate_bets(original_hands))),
        }
    with (output / "hands.jsonl").open("w", encoding="utf8") as stream:
        for hand in hands:
            stream.write(json.dumps(hand, ensure_ascii=False) + "\n")
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf8"
    )
    lines = [
        f"# {session.name}",
        "",
        "Фрагменты наблюдений, не полная история ставок.",
        "Имена — чтения OCR, не новые профили БД. Отсутствие карт не означает фолд.",
        "Суммы подтверждаются двумя чтениями; разность не определяет тип действия.",
        "",
    ]
    for hand in hands:
        warning_ru = {
            "capture_boundary": "прерывался захват",
            "gap_in_observations": "разрыв наблюдений",
            "hand_id_unknown": "терялся номер раздачи",
            "layout_unknown": "терялись места стола",
            "board_conflict": "борд исчез или противоречит предыдущему",
            "action_after_fold": "действие после наблюдённого сброса",
            "blind_conflict": "противоречивые места блайндов",
            "dealer_conflict": "противоречивое место дилера",
        }
        lines += [
            f"## Раздача {hand['hand_id']}",
            "",
            "Места с признаками участия: "
            + ", ".join(str(int(s) + 1) for s in hand["participants"]),
            "Пробелы/противоречия: "
            + (
                ", ".join(warning_ru.get(w, w) for w in hand["warnings"])
                or "не отмечены; полнота не доказана"
            ),
            "",
        ]
        for participant in hand["participants"].values():
            names = ", ".join(participant.get("observed_names", {})) or "имя не подтверждено"
            lines.append(f"- Место {participant['seat_index'] + 1}, чтения имени: {names}.")
        lines.append("")
        for event in hand["events"]:
            seat = event.get("seat_index")
            label = {
                "action_label": "Надпись действия",
                "blind_label": "Обязательный блайнд",
                "dealer_observed": "Дилер",
                "bet_amount": "Сумма возле игрока",
                "pot_amount": "Банк",
                "street_observed": "Улица",
            }[event["kind"]]
            value = event.get("action", event.get("blind", event.get("value", event.get("street"))))
            if event["kind"] == "dealer_observed":
                value = "маркер D"
            action_ru = {
                "small_blind": "малый блайнд",
                "big_blind": "большой блайнд",
                "fold": "сброс",
                "check": "чек",
                "call": "колл",
                "bet": "ставка",
                "raise": "рейз",
            }
            street_ru = {"preflop": "префлоп", "flop": "флоп", "turn": "тёрн", "river": "ривер"}
            value = action_ru.get(value, street_ru.get(value, value))
            source = (
                f"[кадр {event['frame_id']}]({Path(event['image']).as_posix()})"
                if event["image"]
                else f"кадр {event['frame_id']} (изображения нет)"
            )
            lines.append(
                f"- {source}: {label}, место {seat + 1 if seat is not None else '—'}, "
                f"{value}; улица {street_ru.get(event.get('street'), 'не подтверждена')}."
            )
            if event.get("resumed_observations"):
                lines[-1] += (
                    f" Объединено коротких пропусков OCR: {len(event['resumed_observations'])}."
                )
            if event.get("observed_delta") is not None:
                lines[-1] += f" Изменение видимой суммы: {event['observed_delta']:+g}."
        lines.append("")
    lines += ["## Сопоставление блайндов с суммами", ""]
    for check in blind_checks:
        status = {
            "same_frame_amount_confirmed": "сумма совпала на двух кадрах",
            "amount_conflict": "суммы противоречат друг другу",
            "amount_unknown": "сумма не подтверждена",
        }[check["status"]]
        blind_name = {"small_blind": "малый блайнд", "big_blind": "большой блайнд"}[check["blind"]]
        amount_text = (
            check["visible_amount"] if check["visible_amount"] is not None else "неизвестно"
        )
        lines.append(
            f"- Раздача {check['hand_id']}, место {check['seat_index'] + 1}: "
            f"{blind_name}, {status}; значение {amount_text}. "
            "Это видимая сумма, размер обязательного взноса ещё не доказан."
        )
    (output / "timeline.md").write_text("\n".join(lines), encoding="utf8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sessions", nargs="*", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/hud/hand_replays"))
    parser.add_argument(
        "--dense-bets",
        action="store_true",
        help="Read bets on every saved image; OCR needs Tesseract and Russian data",
    )
    parser.add_argument(
        "--refresh-labels",
        type=Path,
        help="Reuse observations.jsonl from dense-bets; requires exactly one source session",
    )
    parser.add_argument(
        "--refresh-cards",
        action="store_true",
        help="Also rerun card recognition with --refresh-labels",
    )
    parser.add_argument(
        "--recover-amounts",
        action="store_true",
        help="Retry unknown currency labels with --refresh-labels",
    )
    args = parser.parse_args()
    if args.recover_amounts and not args.refresh_labels:
        parser.error("--recover-amounts requires --refresh-labels")
    if args.refresh_cards and not args.refresh_labels:
        parser.error("--refresh-cards requires --refresh-labels")
    if args.refresh_labels and (len(args.sessions) != 1 or args.dense_bets):
        parser.error("--refresh-labels requires one session and cannot combine with --dense-bets")
    if args.dense_bets or args.refresh_labels:
        configure_ocr()
    sessions = args.sessions or sorted(Path("artifacts/hud/sessions").glob("session_*"))
    output = args.output / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output.mkdir(parents=True)
    sources = [Path(__file__), *Path("src/poker/hud").glob("*.py")]
    source_hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    summaries = []
    for session in sessions:
        result = replay(
            session,
            output / session.name,
            args.dense_bets,
            args.refresh_labels,
            args.refresh_cards,
            args.recover_amounts,
        )
        summaries.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    manifest = {
        "schema_version": 1,
        "summaries": summaries,
        "source_sha256": source_hashes,
        "input_sha256": {
            str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest()
            for session in sessions
            for p in session.glob("events.jsonl*")
        },
    }
    if args.refresh_labels:
        manifest["input_sha256"][str(args.refresh_labels.resolve())] = hashlib.sha256(
            args.refresh_labels.read_bytes()
        ).hexdigest()
    (output / "summary.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf8"
    )
    print(output.resolve(), flush=True)


if __name__ == "__main__":
    main()
