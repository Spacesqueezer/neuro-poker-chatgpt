"""Audit exact-frame request drafts; never call the model or write player statistics."""

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import cv2

from poker.hud.decision_stream import DecisionStream, proposal, request_errors
from poker.hud.hand import HandObservation
from poker.hud.hand_reconstruction import HandReconstructor
from poker.hud.models import PlayerObservation
from poker.hud.recognition import configure_ocr
from poker.hud.seat_evidence import (
    ConfirmedStacks,
    confirmed_bets,
    occupancy_evidence,
    participation,
    read_stack,
)
from poker.hud.seat_occupancy import (
    EmptySeatTracker,
    clear_empty_identities,
    filter_empty_players,
    read_empty_seat,
)
from poker.hud.state import TableState

if __package__:
    from .replay_hud_hands import cached_rows
else:
    from replay_hud_hands import cached_rows


def matched_controls(row, control):
    return (
        row["frame_id"] == control["frame_id"]
        and row["captured_at"] == control["captured_at"]
        and row.get("window") == control.get("window")
        and row.get("client_rect") == control.get("client_rect")
        and bool(row.get("image"))
        and Path(row["image"]).resolve() == Path(control["image"]).resolve()
    )


REASONS_RU = {
    "awaiting_second_frame": "нет второго совпадающего состояния",
    "betting_state_unverified": "история ставок не подтверждена",
    "table_membership_unverified": "участники раздачи не подтверждены",
    "stacks_unverified": "не все необходимые стеки подтверждены",
    "can_all_in_unknown": "неизвестна доступность all-in",
    "max_raise_amount_unknown": "неизвестен максимум рейза",
    "min_raise_amount_unknown": "неизвестен минимум рейза",
    "player_cards_dealt_unknown": "не подтверждено, кому сданы карты",
    "player_current_bet_unknown": "неизвестны ставки части мест",
    "player_is_active_unknown": "неизвестно, кто ещё участвует",
    "player_stack_unknown": "неизвестны стеки части мест",
    "total_pot_unknown": "неизвестен банк",
    "hand_id_unknown": "не подтверждён номер раздачи",
    "call_amount_needed_unknown": "неизвестна сумма колла",
    "cards_not_confident": "неуверенное чтение карт",
    "cards_unknown_or_invalid": "неполный или противоречивый набор карт",
    "turn_continuity_unverified": "между OCR-замерами кнопок возможны пропущенные изменения",
}


def unknown_fields(payload):
    paths = [key for key, value in payload.items() if value is None]
    for player in payload["players"]:
        paths.extend(
            f"players[seat={player['seat_index']}].{key}"
            for key, value in player.items()
            if value is None
        )
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    parser.add_argument("observations", type=Path)
    parser.add_argument("controls", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/hud/request_audits"))
    parser.add_argument(
        "--read-stacks", action="store_true", help="Read and confirm stacks on exact source images"
    )
    args = parser.parse_args()
    if args.read_stacks:
        configure_ocr()
    controls = {}
    for line in args.controls.read_text(encoding="utf8").splitlines():
        record = json.loads(line)
        if record["frame_id"] in controls:
            raise ValueError("Duplicate control frame")
        controls[record["frame_id"]] = record
    output = args.output / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output.mkdir(parents=True)
    state, stream = TableState(), DecisionStream()
    counts, blockers = Counter(), Counter()
    previous_cards = previous_window = None
    previous_bet_row = None
    hands, stacks = HandReconstructor(), ConfirmedStacks()
    empty = EmptySeatTracker()
    lines = [
        "# Проверка JSON в моменты нашего хода",
        "",
        "Все запросы — диагностические черновики. Модель не вызывается.",
        "",
    ]
    for row in cached_rows(args.session, args.observations):
        if row["kind"] != "frame":
            previous_bet_row = None
            state, stream = TableState(), DecisionStream()
            hands.interrupt("capture_boundary")
            stacks = ConfirmedStacks()
            empty = EmptySeatTracker()
            continue
        hands.update(row)
        bet_facts = confirmed_bets(row, previous_bet_row, hands)
        previous_bet_row = row
        if hands.current is None:
            stacks = ConfirmedStacks()
        card_state = row["context"].get("decision_hand", {})
        card_key = (
            tuple(card_state.get("hero", [])),
            tuple(card_state.get("board", [])),
            card_state.get("valid"),
        )
        window = (row.get("window"), tuple(row.get("client_rect", [])))
        if previous_window is not None and previous_window != window:
            state, stream = TableState(), DecisionStream()
        if previous_cards is not None and previous_cards != card_key:
            stream.reset()
            counts["card_transition_resets"] += 1
        previous_cards, previous_window = card_key, window
        control = controls.get(row["frame_id"])
        if control is None:
            continue
        if not matched_controls(row, control):
            raise ValueError(f"Source mismatch for frame {row['frame_id']}")
        counts["source_frames"] += 1
        if counts["source_frames"] % 100 == 0:
            print(f"{counts['source_frames']} source frames", flush=True)
        context = row["context"]
        current = control["controls"]
        state.update(
            [PlayerObservation(**p) for p in row.get("players", [])], tuple(row["client_rect"][-2:])
        )
        stack_readings = {}
        stack_facts = {}
        frame = cv2.imread(row["image"])
        if frame is None:
            raise ValueError(f"Missing source image: {row['image']}")
        if args.read_stacks:
            stack_readings = {
                slot["seat_index"]: read_stack(frame, slot["roi"])
                for slot in context["table_signals"].get("slots", [])
            }
            stack_facts = stacks.update(row, stack_readings)
        slots = context["table_signals"].get("slots", [])
        participant_facts = participation(hands)
        occupied = occupancy_evidence(participant_facts, stack_facts, stack_readings)
        occupied.update(
            {
                s["seat_index"]: {}
                for s in slots
                if s.get("card_back_evidence", {}).get("present") is True
            }
        )
        confirmed_empty = empty.update(
            row, {s["seat_index"]: read_empty_seat(frame, s["roi"]) for s in slots}, occupied
        )
        cleared = clear_empty_identities(state, slots, confirmed_empty)
        counts["cleared_empty_identities"] += len(cleared)
        if not current["flags"]:
            stream.reset()
            counts["not_our_turn"] += 1
            continue
        data = context["decision_hand"]
        hand = HandObservation(
            hero=tuple(data.get("hero", [])),
            board=tuple(data.get("board", [])),
            valid=data.get("valid", False),
            my_turn=True,
        )
        joined = {**context, "table_signals": {**context["table_signals"], "controls": current}}
        payload = proposal(hand, state.seats.values(), joined)
        participant_facts = participation(hands)
        for player in payload["players"]:
            seat = player["seat_index"]
            if seat in participant_facts:
                player.update({k: participant_facts[seat][k] for k in ("cards_dealt", "is_active")})
            if args.read_stacks:
                player["stack"] = stack_facts.get(seat, {}).get("value")
        payload, excluded = filter_empty_players(payload, confirmed_empty, hands.current)
        for player in payload["players"]:
            player["current_bet"] = bet_facts.get(player["seat_index"], {}).get("value")
        counts["empty_slots_excluded"] += len(excluded)
        occupancy = occupancy_evidence(participant_facts, stack_facts, stack_readings)
        counts["occupied_seat_observations"] += len(occupancy)
        counts["complete_occupied_tables"] += len(occupancy) == 7
        counts["participant_fields_confirmed"] += sum(
            p["cards_dealt"] is True for p in payload["players"]
        )
        counts["stacks_confirmed"] += (
            sum(p["stack"] is not None for p in payload["players"]) if args.read_stacks else 0
        )
        counts["bets_confirmed"] += sum(p["current_bet"] is not None for p in payload["players"])
        meta = {key: row[key] for key in ("frame_id", "captured_at", "window", "client_rect")}
        identity = context.get("hand_id", {})
        key = str(identity.get("value", "")) if identity.get("confidence", 0) >= 80 else ""
        result = stream.update(
            payload,
            meta,
            key,
            cards_valid=hand.valid,
            blockers=(
                "table_membership_unverified",
                "betting_state_unverified",
                "stacks_unverified",
                "turn_continuity_unverified",
            ),
            now=datetime.fromisoformat(row["captured_at"]),
        )
        counts["our_turn_frames"] += 1
        if result is None:
            counts["duplicate_drafts"] += 1
            continue
        reasons = result["blockers"]
        blockers.update(reasons)
        folder = output / f"frame_{row['frame_id']:08d}"
        folder.mkdir()
        (folder / "request.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf8"
        )
        evidence = {
            **result,
            "image": row["image"],
            "source_match": True,
            "field_sources": {
                "cards": "same_frame_card_replay",
                "controls": "same_frame_control_replay",
                "players": "sequential_names_from_source_frames",
                "current_bet": "two_consecutive_frames_same_hand_board_window_and_roi",
                "stack_confidence": "two_frames_min_word_score_85"
                if args.read_stacks
                else "not_recorded_separately",
            },
            "context": joined,
            "raw_players": row.get("players", []),
            "participation_evidence": participant_facts,
            "occupancy_evidence": occupancy,
            "empty_seat_evidence": confirmed_empty,
            "excluded_empty_seats": excluded,
            "cleared_identity_keys": cleared,
            "stack_readings": stack_readings,
            "stack_confirmations": stack_facts,
            "bet_confirmations": bet_facts,
            "field_errors": request_errors(payload),
            "unknown_fields": unknown_fields(payload),
        }
        (folder / "evidence.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf8"
        )
        counts["drafts"] += 1
        counts["would_send"] += result["would_send"]
        lines += [
            f"## Кадр {row['frame_id']}, раздача {key or 'неизвестна'}",
            "",
            f"[Изображение]({Path(row['image']).as_posix()}) · [JSON]({folder.name}/request.json)",
            f"Повторных совпадений состояния: {result['confirmations']}.",
            "Причины блокировки: "
            + ", ".join(REASONS_RU.get(reason, reason) for reason in reasons),
            "",
        ]
    summary = {
        "schema_version": 1,
        **counts,
        "blockers": dict(blockers),
        "model_called": False,
        "input_sha256": {
            str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [args.observations, args.controls, *args.session.glob("events.jsonl*")]
        },
        "source_sha256": {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [Path(__file__), *Path("src/poker/hud").glob("*.py")]
        },
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf8"
    )
    (output / "review.md").write_text("\n".join(lines), encoding="utf8")
    print(json.dumps(summary, ensure_ascii=False))
    print(output.resolve())


if __name__ == "__main__":
    main()
