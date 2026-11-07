"""Inspect recorded street boundaries without treating them as final betting totals."""

import argparse
import json
from pathlib import Path

from poker.hud.hand_reconstruction import HandReconstructor
from poker.hud.session_images import saved_frame_path


def audit(session):
    events = sorted(
        (
            json.loads(line)
            for path in session.glob("events.jsonl*")
            for line in path.read_text(encoding="utf8").splitlines()
            if line.strip()
        ),
        key=lambda e: e["at"],
    )
    cards = {e["frame_id"]: e["hand"] for e in events if e["kind"] == "cards"}
    frames = {e["frame_id"]: e for e in events if e["kind"] == "frame"}
    tracker = HandReconstructor()
    epoch = None
    transitions = []
    for event in events:
        if event["kind"] in {"target", "window", "pause"}:
            tracker.interrupt("capture_boundary")
        if event["kind"] not in {"names", "decision_dry_run"}:
            continue
        if event.get("evidence_epoch") != epoch:
            tracker = HandReconstructor()
            epoch = event.get("evidence_epoch")
        tracker.update(event)
        if not tracker.current:
            continue
        for boundary in tracker.current["events"]:
            if (
                boundary["kind"] != "street_observed"
                or boundary["frame_id"] != event["frame_id"]
                or boundary["previous_street"] in (None, boundary["street"])
            ):
                continue
            key = (tracker.current["hand_id"], boundary["frame_id"])
            if any((t["hand_id"], t["boundary"]["frame_id"]) == key for t in transitions):
                continue
            transitions.append(dict(hand_id=key[0], boundary=boundary))
    # These surrounding frames are retrospective review evidence, never attached
    # to an earlier request and never used to assert complete action ordering.
    for transition in transitions:
        b = transition["boundary"]
        low = b["previous_street_source"]["frame_id"]
        high = b["frame_id"]
        selected = []
        for number in sorted(frames):
            if not low <= number <= high:
                continue
            frame = frames[number]
            path = saved_frame_path(session, number)
            selected.append(
                dict(
                    frame_id=number,
                    captured_at=frame["captured_at"],
                    image=str(path.resolve()) if path.is_file() else None,
                    card_reading=cards.get(number),
                )
            )
        transition["review_frames"] = selected
    return transitions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not list(args.session.glob("events.jsonl*")):
        parser.error("Session must contain recorded events")
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Choose an empty output directory")
    transitions = audit(args.session)
    args.output.mkdir(parents=True, exist_ok=True)
    result = dict(
        session=args.session.name,
        transitions=transitions,
        model_called=False,
        player_db_written=False,
        semantics="retrospective_review_not_final_contributions",
    )
    (args.output / "boundaries.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8"
    )
    lines = [
        f"# Границы улиц: {args.session.name}",
        "",
        "Переход подтверждён двумя одинаковыми чтениями борда. Это не доказывает, "
        "что ставки прошлого кадра были итоговыми. Между текстовыми чтениями могли "
        "произойти действия или анимация. Соседние кадры — материал ретроспективной "
        "проверки; в более ранние запросы они не подставляются.",
        "",
        "| Раздача | Переход | Последний кадр прежней улицы по OCR | Подтверждающая пара |",
        "| --- | --- | ---: | --- |",
    ]
    for t in transitions:
        b = t["boundary"]
        pair = ", ".join(str(f["frame_id"]) for f in b["confirmation_frames"])
        lines.append(
            f"| {t['hand_id']} | {b['previous_street']} → {b['street']} | "
            f"{b['previous_street_source']['frame_id']} | {pair} |"
        )
    lines += [
        "",
        "Пути сохранённых изображений и исходные чтения карт находятся в "
        "`boundaries.json → transitions → review_frames`. Отсутствующее изображение "
        "обозначено null. Итоговые взносы не восстановлены, модель и БД не вызывались.",
    ]
    (args.output / "review.md").write_text("\n".join(lines) + "\n", encoding="utf8")
    print(json.dumps(dict(session=args.session.name, transitions=len(transitions))))


if __name__ == "__main__":
    main()
