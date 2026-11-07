"""Offline contract audit. Never invokes a neural policy or writes player statistics."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from poker.api import ActionDecision, play_hand
from poker.game.actions import PlayerAction
from poker.hud.advisor_state import build_advisor_draft
from poker.hud.hand_reconstruction import HandReconstructor
from poker.learning.advisor_adapters import from_engine
from poker.learning.observation import LearningObservationEncoder


class Caller:
    def choose_action(self, state, legal):
        action = PlayerAction.CHECK if PlayerAction.CHECK in legal.actions else PlayerAction.CALL
        return ActionDecision(action, legal.call_amount if action == PlayerAction.CALL else 0)


def rebuild_hud(events):
    """Keep asynchronous name/fast histories separate, including their rejected results."""
    trackers = {kind: HandReconstructor() for kind in ("names", "fast_table")}
    epochs = {}
    for event in events:
        kind = event["kind"]
        if kind in ("target", "window", "pause", "hero_seat_changed"):
            trackers = {name: HandReconstructor() for name in trackers}
        if kind == "fast_table_error":
            trackers["fast_table"] = HandReconstructor()
        if kind not in ("names", "fast_table", "decision_dry_run"):
            continue
        stream = event.get("decision_source", "names") if kind == "decision_dry_run" else kind
        if stream not in trackers:
            raise ValueError(f"Unsupported decision source: {stream}")
        if epochs.get(stream) != event.get("evidence_epoch"):
            trackers[stream] = HandReconstructor()
            epochs[stream] = event.get("evidence_epoch")
        tracker = trackers[stream]
        if (kind == "fast_table" and event.get("accepted") is not True) or (
            kind == "names" and event.get("live_evidence_rejected")
        ):
            # LiveEvidence.reset() discards this fragment; retaining it here
            # would invent a different history and additional blockers on replay.
            trackers[stream] = HandReconstructor()
            continue
        tracker.update(event)
        if kind == "decision_dry_run":
            yield (
                event,
                build_advisor_draft(
                    event, tracker, event, event.get("context", {}), event.get("live_evidence", {})
                ),
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--inspect-weights", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Choose an empty output directory; existing audits are preserved")
    args.output.mkdir(parents=True, exist_ok=True)
    events = sorted(
        [
            json.loads(line)
            for p in args.session.glob("events.jsonl*")
            for line in p.read_text(encoding="utf8").splitlines()
        ],
        key=lambda e: e["at"],
    )
    hud = []
    for e, diagnostic in rebuild_hud(events):
        if diagnostic["observation"] is not None:
            diagnostic["observation"]["evidence"].update(
                session=str(args.session.resolve()),
                source_event_at=e["at"],
                raw_request=e["request"],
                live_evidence=e.get("live_evidence", {}),
            )
        hud.append(diagnostic)
    engine = []
    features = None
    for seed in range(10):

        def observer(state, legal, decision, hand_seed=seed):
            nonlocal features
            row = from_engine(
                state,
                legal,
                hand_id=f"seed:{hand_seed}",
                observation_id=str(len(engine)),
                big_blind=2,
                history_complete=True,
            )
            engine.append(dict(observation=row.to_dict(), blockers=row.blocking_reasons()))
            if features is None:
                features = LearningObservationEncoder().encode(state).feature_names

        play_hand({f"seat_{n}": Caller() for n in range(6)}, seed=seed, decision_observer=observer)
    weights = []
    if args.inspect_weights:
        import torch

        for directory in ("models", "ready_agents", "tournament_winner"):
            for path in sorted(Path(directory).rglob("*.pt")):
                state = torch.load(path, map_location="cpu", weights_only=True)
                weights.append(
                    dict(
                        path=str(path),
                        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                        shapes={k: list(v.shape) for k, v in state.items() if hasattr(v, "shape")},
                    )
                )
    # Count each hand/seat/street once, using its latest available diagnostic.
    coverage = {}
    for diagnostic in hud:
        observation = diagnostic["observation"] or {}
        fragment = observation.get("evidence", {}).get("hand_fragment", {})
        for player in fragment.get("contribution_coverage", {}).get("players", []):
            for street in player["streets"]:
                coverage[(observation["hand_id"], player["seat"], street["street"])] = street
    contribution_summary = dict(
        hand_seat_streets=len(coverage),
        with_observed_amount=sum(s["observed_count"] > 0 for s in coverage.values()),
        with_decrease=sum(bool(s["decrease_sources"]) for s in coverage.values()),
        with_verified_final=sum(s["final_total"] is not None for s in coverage.values()),
        blockers=dict(Counter(b for s in coverage.values() for b in s["blockers"])),
    )
    summary = dict(
        session=args.session.name,
        hud_drafts=len(hud),
        hud_structurally_clear=sum(not r["blockers"] for r in hud),
        hud_history_observations=sum(len((r["observation"] or {}).get("history", [])) for r in hud),
        hud_known_folds=sum(
            p["folded"] is not None
            for r in hud
            for p in (r["observation"] or {}).get("players", [])
        ),
        hud_known_all_in=sum(
            p["all_in"] is not None
            for r in hud
            for p in (r["observation"] or {}).get("players", [])
        ),
        hud_blockers=dict(Counter(b for r in hud for b in r["blockers"])),
        contribution_coverage=contribution_summary,
        engine_observations=len(engine),
        engine_invalid=sum(bool(r["blockers"]) for r in engine),
        legacy_features=features,
        weights=weights,
        model_called=False,
        player_db_written=False,
    )
    for name, data in (("summary.json", summary), ("hud.json", hud), ("engine.json", engine)):
        (args.output / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf8"
        )
    c = contribution_summary
    (args.output / "contributions.md").write_text(
        f"# Покрытие взносов: {args.session.name}\n\n"
        f"Проверено черновиков: {len(hud)}. Модель не вызывалась, БД не изменялась.\n\n"
        "Единица подсчёта ниже — уникальная тройка раздача/место/улица из доступных "
        "черновиков. Взято её последнее диагностическое состояние. Это не число действий "
        "и не полный перечень раздач сессии.\n\n"
        f"- Всего троек: {c['hand_seat_streets']}.\n"
        f"- Есть подтверждённое чтение суммы: {c['with_observed_amount']}.\n"
        f"- Наблюдалось уменьшение суммы: {c['with_decrease']}.\n"
        f"- Подтверждён итог улицы: {c['with_verified_final']}.\n\n"
        "Последняя видимая сумма не считается итогом улицы. Уменьшение не объявляется "
        "возвратом: возможны анимация или ошибка чтения. Отсутствующая сумма не равна нулю. "
        "Начальные обязательные взносы и итоги улиц пока не верифицируются; полный вклад "
        "за раздачу остаётся неизвестным. Это ограничение реализации, а не доказательство "
        "отсутствия нужных кадров в сессии.\n\n"
        "Источники и причины по каждому месту: hud.json → observation.evidence."
        "hand_fragment.contribution_coverage. Суммы выражены в единицах observation.quantum.\n",
        encoding="utf8",
    )
    print(
        json.dumps(
            {
                k: v
                for k, v in summary.items()
                if k not in ("legacy_features", "weights", "hud_blockers")
            }
        )
    )


if __name__ == "__main__":
    main()
