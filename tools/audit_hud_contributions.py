"""Reconcile observed stack/bet endpoints without calling a model or writing player DB."""

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from poker.hud.action_stack_audit import audit_action_stacks
from poker.hud.contribution_reconciliation import reconcile_observations
from poker.hud.hand_reconstruction import HandReconstructor
from poker.hud.pot_movements import pot_movements
from poker.hud.return_audit import audit_returns
from poker.hud.session_images import saved_frame_path


def select_hand_events(events, hand_id, padding_seconds=5):
    if not math.isfinite(padding_seconds) or not 0 <= padding_seconds <= 30:
        raise ValueError("Replay padding must be finite and between 0 and 30 seconds")
    matches = [
        e
        for e in events
        if e["kind"] == "names"
        and str(e.get("context", {}).get("hand_id", {}).get("value")) == hand_id
        and e.get("context", {}).get("hand_id", {}).get("confidence", 0) >= 80
    ]
    if not matches:
        raise ValueError("No confident observations of this hand in the session")
    times = [datetime.fromisoformat(e["captured_at"]) for e in matches]
    padding = timedelta(seconds=padding_seconds)
    low, high = min(times) - padding, max(times) + padding
    selected = [
        e
        for e in events
        if e["kind"] in {"frame", "target", "window", "pause"}
        and low <= datetime.fromisoformat(e.get("captured_at") or e["at"]) <= high
    ]
    return sorted(selected, key=lambda e: e.get("captured_at") or e["at"])


def replay_hand(session, events, selected, output):
    import cv2

    from poker.hud.cards import find_cards
    from poker.hud.client_id import read_hand_id
    from poker.hud.hand import observe
    from poker.hud.recognition import configure_ocr, layout_panels
    from poker.hud.seat_evidence import read_stack
    from poker.hud.table_signals import (
        anchored_pot,
        read_action_label,
        read_bets,
        read_blind_label,
        read_settlement_label,
    )

    configure_ocr()
    epochs = sorted(
        {
            (e["frame_id"], e["evidence_epoch"])
            for e in events
            if "frame_id" in e and "evidence_epoch" in e
        }
    )
    rows, missing = [], []
    with (output / "observations.jsonl").open("w", encoding="utf8") as stream:
        for event in selected:
            if event["kind"] != "frame":
                row = event
            else:
                path = saved_frame_path(session, event["frame_id"])
                image = cv2.imread(str(path)) if path.is_file() else None
                if image is None:
                    missing.append(event["frame_id"])
                    continue
                rois = layout_panels(image)
                slots, stacks = [], {}
                if len(rois) == 7:
                    bets = read_bets(image, rois)
                    for seat, roi in enumerate(rois):
                        settlement = read_settlement_label(image, roi)
                        slots.append(
                            dict(
                                seat_index=seat,
                                roi=roi,
                                current_bet=None if settlement else bets[seat]["value"],
                                bet_evidence=bets[seat],
                                action_label=read_action_label(image, roi),
                                blind_label=read_blind_label(image, roi),
                                settlement_label=settlement,
                            )
                        )
                        stacks[str(seat)] = read_stack(image, roi, read_status=False)
                known_epochs = [epoch for number, epoch in epochs if number <= event["frame_id"]]
                hand = observe(find_cards(image)).to_dict()
                row = {
                    k: event.get(k)
                    for k in ("frame_id", "captured_at", "window", "client_rect", "at")
                }
                row.update(
                    kind="names",
                    image=str(path.resolve()),
                    evidence_epoch=known_epochs[-1] if known_epochs else None,
                    context=dict(
                        hand_id=read_hand_id(image),
                        decision_hand=hand,
                        hero_visible=len(hand["hero"]) == 2,
                        stack_readings=stacks,
                        table_signals={"slots": slots, "pot": anchored_pot(image)},
                    ),
                )
            encoded = json.dumps(row, ensure_ascii=False)
            # OCR dataclasses contain tuples; downstream audits must see exactly
            # the same representation as a later reload of observations.jsonl.
            rows.append(json.loads(encoded))
            stream.write(encoded + "\n")
            stream.flush()
            if len(rows) % 25 == 0:
                print(f"Replayed {len(rows)} observations", flush=True)
    (output / "replay_sources.json").write_text(
        json.dumps(
            dict(
                session=str(session.resolve()),
                missing_frames=missing,
                observed_frames=sum(r["kind"] == "names" for r in rows),
                boundaries=sum(r["kind"] != "names" for r in rows),
                semantics="retrospective_image_replay",
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf8",
    )
    return rows


def action_stack_results(events):
    tracker = HandReconstructor()
    epoch = None
    for row in events:
        if row.get("kind") in {"target", "window", "pause"}:
            tracker.interrupt("capture_boundary")
        elif row.get("kind", "names") == "names":
            if row.get("evidence_epoch") != epoch:
                tracker.interrupt("evidence_epoch_changed")
                epoch = row.get("evidence_epoch")
            tracker.update(row)
    return audit_action_stacks(events, list(tracker.hands.values()))


def scope_replay_result(result, hand_id):
    """Keep boundary captures for reconstruction, but report only the requested hand."""
    scoped = dict(result)
    excluded = {}
    for key in (
        "points",
        "intervals",
        "pot_movements",
        "action_stack_intervals",
        "return_candidates",
    ):
        items = result.get(key, [])
        scoped[key] = [item for item in items if str(item.get("hand_id")) == hand_id]
        excluded[key] = len(items) - len(scoped[key])
    scoped["excluded_neighbor_results"] = excluded
    return scoped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replay-hand", help="Re-read saved images around a recorded hand id")
    parser.add_argument(
        "--replay-padding-seconds",
        type=float,
        default=5,
        help="Extra capture time around confident text samples (0-30, default: 5)",
    )
    args = parser.parse_args()
    sources = list(args.session.glob("events.jsonl*"))
    if not sources:
        parser.error("Session must contain recorded events")
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Choose an empty output directory")
    events = sorted(
        (
            json.loads(line)
            for p in sources
            for line in p.read_text(encoding="utf8").splitlines()
            if line.strip()
        ),
        key=lambda e: e["at"],
    )
    selected = None
    if args.replay_hand:
        try:
            selected = select_hand_events(events, args.replay_hand, args.replay_padding_seconds)
        except ValueError as error:
            parser.error(str(error))
    args.output.mkdir(parents=True, exist_ok=True)
    if selected is not None:
        events = replay_hand(args.session, events, selected, args.output)
    for event in events:
        if event["kind"] == "names":
            image = saved_frame_path(args.session, event["frame_id"])
            event["image"] = str(image.resolve()) if image.is_file() else None
    result = reconcile_observations(events)
    result["pot_movements"] = pot_movements(events)
    result["action_stack_intervals"] = action_stack_results(events)
    result["return_candidates"] = audit_returns(events)
    if args.replay_hand:
        result = scope_replay_result(result, args.replay_hand)
    result["session"] = args.session.name
    result["replayed_hand"] = args.replay_hand
    result["replay_padding_seconds"] = args.replay_padding_seconds if args.replay_hand else None
    result["summary"] = dict(
        points=len(result["points"]),
        intervals=len(result["intervals"]),
        return_candidates=len(result["return_candidates"]),
        statuses=dict(Counter(i["status"] for i in result["intervals"])),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "reconciliation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8"
    )
    (args.output / "review.md").write_text(render_report(result), encoding="utf8")
    print(json.dumps(result["summary"]))


def render_report(result):
    lines = [
        f"# Сверка стеков и ставок: {result['session']}",
        "",
        "Каждая граница участка подтверждена двумя разными кадрами с одинаковыми "
        "стеком и ставкой. Суммы ниже — сотые денежной единицы (quantum=0.01). "
        "Сравниваются уменьшение стека и рост видимой ставки на одной улице. "
        "Совпадение не доказывает полноту истории или размер отдельного действия.",
        "",
        "| Раздача | Место | Кадры границ | Уменьшение стека | Рост ставки | "
        "Разница | Пропуски внутри |",
        "| --- | ---: | --- | ---: | ---: | ---: | --- |",
    ]
    if result.get("replayed_hand"):
        lines[1:1] = [
            "",
            f"Раздача: {result['replayed_hand']}. Финансовые результаты соседних рук "
            "исключены из таблиц; их исходные кадры сохранены для проверки границ.",
        ]
    for i in result["intervals"]:
        before = i["before"]["confirmation_frames"][-1]["frame_id"]
        after = i["after"]["confirmation_frames"][-1]["frame_id"]
        lines.append(
            f"| {i['hand_id']} | {i['seat']} | {before} → {after} | "
            f"{i['stack_decrease']} | {i['street_bet_increase']} | {i['residual']} | "
            f"{'да' if i['missing_intermediate_readings'] else 'нет'} |"
        )
    lines += [
        "",
        "Отсутствующая ставка не равна нулю. После смены улицы, раздачи, окна, "
        "геометрии, эпохи, выплаты или разрыва захвата сверка начинается заново. "
        "Отрицательные изменения остаются кандидатами возврата/коррекции. "
        "Полный вклад за раздачу и суммы действий не заполняются.",
        "",
        "Источники, исходные суммы и пары кадров находятся в reconciliation.json. "
        "Это офлайн-диагностика; модель и БД не вызываются.",
    ]
    lines += [
        "",
        "## Изменения видимого банка",
        "",
        "Оба значения подтверждены парой кадров. Это наблюдения интерфейса, "
        "а не окончательные суммы расчёта: анимация может держать промежуточное "
        "значение несколько кадров. Уменьшение банка не означает автоматически "
        "возврат, комиссию или выплату. Причина остаётся неизвестной.",
        "",
        "| Раздача | Кадры | Было | Стало | Изменение |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for move in result.get("pot_movements", []):
        before, after = move["before"], move["after"]
        first = before["confirmation_frames"][-1]["frame_id"]
        last = after["confirmation_frames"][-1]["frame_id"]
        frames = f"{first} → {last}"
        lines.append(
            f"| {move['hand_id']} | {frames} | {before['value']} | {after['value']} | "
            f"{move['delta']:+d} |"
        )
    lines += [
        "",
        "## Стеки вокруг надписей действий",
        "",
        "Обе границы подтверждены парой кадров. Допускается переход улицы; "
        "используются кадры ПОСЛЕ действия. Разность стеков не доказывает сумму "
        "отдельного действия: пропуски могут скрывать другие движения фишек. "
        "contributed_delta остаётся null; в модель и БД эти числа не переносятся. "
        "Время до последнего кадра подтверждения считается от кадра надписи; "
        "это не задержка OCR и не измерение времени от реального клика игрока.",
        "",
        "| Место | Надпись | Кадр | Было | Стало | Уменьшение | "
        "До подтверждения, мс | Другие действия |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in result.get("action_stack_intervals", []):
        action = item["action"]
        competing = "да" if item["competing_actions"] else "не наблюдались"
        delay = item.get("confirmation_timing", {}).get("capture_span_after_action_ms", "—")
        lines.append(
            f"| {item['seat']} | {action['action']} | {action['frame_id']} | "
            f"{item['before']['stack']} | {item['after']['stack']} | "
            f"{item['stack_decrease']} | {delay} | {competing} |"
        )
    lines += [
        "",
        "## Кандидаты возврата ставки",
        "",
        "Рост стека и исходные ставки подтверждены парами кадров; противник "
        "дважды показал фолд. Банк до изменения подтверждён парой кадров и "
        "уменьшился не меньше, чем вырос стек. Рост равен превышению над другой "
        "наибольшей учтённой ставкой. Пропуски OCR сохраняются. Отдельно можно "
        "учесть нулевую ставку на текущей улице, если фолд на предыдущей улице "
        "подтверждён двумя кадрами без последующих противоречий. Это не нулевой "
        "вклад за всю раздачу. returned_amount остаётся null. Выплата и комиссия "
        "не вычисляются.",
        "",
        "| Раздача | Место | Кадры | Кандидат возврата | Пропуски OCR | "
        "Не учтены после проверки фолдов |",
        "| --- | ---: | --- | ---: | --- | --- |",
    ]
    fold_notes = []
    for item in result.get("return_candidates", []):
        first = item["before"]["confirmation_frames"][-1]["frame_id"]
        last = item["after"]["confirmation_frames"][-1]["frame_id"]
        unknown = ", ".join(map(str, item["unknown_other_bet_seats"])) or "нет"
        unresolved = (
            ", ".join(
                map(str, item.get("unknown_accounted_bet_seats", item["unknown_other_bet_seats"]))
            )
            or "нет"
        )
        lines.append(
            f"| {item['hand_id']} | {item['seat']} | {first} → {last} | "
            f"{item['candidate_return']} | {unknown} | {unresolved} |"
        )
        for seat, proof in item.get("earlier_street_fold_evidence", {}).items():
            frames = ", ".join(str(s["frame_id"]) for s in proof["confirmation_frames"])
            fold_notes.append(
                f"Раздача {item['hand_id']}, место {seat}: фолд на предыдущей улице, "
                f"кадры {frames}."
            )
    if fold_notes:
        lines += ["", *fold_notes]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
