"""Project causal hand fragments into advisor diagnostics, never invent full history."""

from copy import deepcopy
from datetime import datetime
from time import perf_counter

from poker.hud.contribution_ledger import contribution_coverage
from poker.hud.seat_evidence import participation
from poker.hud.title_stakes import confirmed_title_stakes
from poker.learning.advisor_adapters import from_hud
from poker.learning.advisor_contract import minor_units


def build_advisor_draft(draft, tracker, source, context, live_facts):
    """Diagnostic sidecar only; invalid input must not interrupt the capture loop."""
    start = perf_counter()
    result = {"model_called": False, "would_send": False, "mode": "diagnostic_only"}
    try:
        title_evidence = live_facts.get("table_stakes", {})
        stakes = confirmed_title_stakes(title_evidence, source, context.get("hand_id", {}))
        observation = from_hud(
            draft["request"],
            hand_id=draft.get("hand_id"),
            hero_seat=context.get("hero_seat", 6),
            observation_id=f"{source['captured_at']}:{source['frame_id']}",
            captured_at=source["captured_at"],
            big_blind=stakes["big_blind"] if stakes else None,
            blockers=draft.get("blockers", ()),
            evidence={
                "frame_id": source["frame_id"],
                "evidence_epoch": source.get("evidence_epoch"),
                "table_stakes": deepcopy(title_evidence),
            },
        )
        if (title_evidence.get("candidate") or {}).get("bomb_pot_schedule_advertised"):
            observation.source_blockers.append("bomb_pot_hand_unverified")
        observation = attach_hand_fragment(
            observation, tracker, {**source, "context": context}, live_facts
        )
        result.update(observation=observation.to_dict(), blockers=observation.blocking_reasons())
    except (ValueError, TypeError, KeyError) as error:
        result.update(
            observation=None, blockers=["advisor_contract_build_failed"], error=str(error)
        )
    result["build_ms"] = round((perf_counter() - start) * 1000, 3)
    return result


def _fresh_pair(fact, source):
    frames = fact.get("confirmation_frames", [])
    now = datetime.fromisoformat(source["captured_at"])
    times = [datetime.fromisoformat(f["captured_at"]) for f in frames]
    return (
        len(frames) >= 2
        and len({f["frame_id"] for f in frames}) == len(frames)
        and frames[-1]["frame_id"] == source["frame_id"]
        and times[-1] == now
        and all(left < right for left, right in zip(times, times[1:], strict=False))
        and all(0 <= (now - at).total_seconds() <= 5 for at in times)
    )


def _contains_future_capture(value, cutoff):
    """Street confirmations and previous sources have their own capture times."""
    if isinstance(value, dict):
        captured = value.get("captured_at")
        if captured is not None and datetime.fromisoformat(captured) > cutoff:
            return True
        return any(_contains_future_capture(child, cutoff) for child in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_future_capture(child, cutoff) for child in value)
    return False


def attach_hand_fragment(observation, tracker, source, live_facts):
    """Require the exact current text capture; future or other-hand trackers are rejected."""
    result = deepcopy(observation)
    hand = tracker.current
    if (
        result.source != "hud"
        or not hand
        or str(hand["hand_id"]) != result.hand_id
        or tracker.source["frame_id"] != source["frame_id"]
        or tracker.source["captured_at"] != result.captured_at
        or tracker.source.get("evidence_epoch") != source.get("evidence_epoch")
        or source["captured_at"] != result.captured_at
        or hand.get("window") != source.get("window")
        or tuple(source.get("client_rect", [])) != tracker.last[2][1]
        or tracker.street != result.street
        or hand.get("board_cards", []) != result.board
    ):
        result.source_blockers.append("hand_fragment_source_mismatch")
        return result
    cutoff = datetime.fromisoformat(result.captured_at)
    if _contains_future_capture(hand["events"], cutoff) or _contains_future_capture(
        hand.get("participants", {}), cutoff
    ):
        result.source_blockers.append("hand_fragment_contains_future")
        return result
    warnings = hand.get("warnings", [])
    result.source_blockers.extend("hand_fragment:" + w for w in warnings)
    result.history = []
    amounts = []
    for e in hand["events"]:
        if e["kind"] == "action_label":
            result.history.append(
                dict(
                    street=e.get("street"),
                    seat=e["seat_index"],
                    action=e["action"],
                    contributed_delta=None,
                    street_to=None,
                    pot_after=None,
                    target_after=None,
                    observed_at=e["captured_at"],
                    frame_id=e["frame_id"],
                    ordering="capture_only",
                    verified=False,
                    evidence=deepcopy(e),
                )
            )
        elif e["kind"] == "bet_amount":
            previous = e.get("previous")
            current = minor_units(e["value"], result.quantum)
            prior = minor_units(previous, result.quantum)
            amounts.append(
                dict(
                    seat=e["seat_index"],
                    street=e["street"],
                    visible_total=current,
                    previous_visible_total=prior,
                    delta_since_previous_reading=None if prior is None else current - prior,
                    semantics="visible_street_total_not_action_size",
                    evidence=deepcopy(e),
                )
            )
    result.history_complete = False
    current_participation = participation(tracker)
    live_stacks = (
        live_facts.get("stack_confirmations", {})
        if str(live_facts.get("hand_id")) == result.hand_id
        else {}
    )
    states = {}
    slots = {
        s["seat_index"]: s
        for s in source.get("context", {}).get("table_signals", {}).get("slots", [])
    }
    for player in result.players:
        fact = current_participation.get(player.seat, {})
        if fact.get("cards_dealt") is True:
            player.cards_dealt = True
        if fact.get("is_active") is True:
            player.folded = False
        elif fact.get("is_active") is False:
            # participation() requires repeated dealt cards AND an observed fold.
            player.folded = True
        stack = live_stacks.get(player.seat, live_stacks.get(str(player.seat), {}))
        if (
            fact.get("cards_dealt") is True
            and not slots.get(player.seat, {}).get("settlement_label")
            and stack.get("value") is not None
            and _fresh_pair(stack, source)
            and minor_units(stack["value"], result.quantum) == player.stack
        ):
            if player.stack > 0 or player.folded is True:
                player.all_in = False
            elif player.stack == 0 and player.folded is False:
                player.all_in = True
        states[str(player.seat)] = dict(participation=deepcopy(fact), stack=deepcopy(stack))
    result.evidence["hand_fragment"] = dict(
        hand_id=hand["hand_id"],
        source={
            k: deepcopy(source.get(k))
            for k in ("frame_id", "captured_at", "window", "client_rect", "evidence_epoch", "image")
        },
        warnings=deepcopy(warnings),
        street_observations=deepcopy([e for e in hand["events"] if e["kind"] == "street_observed"]),
        observed_contributions=amounts,
        contribution_coverage=contribution_coverage(
            amounts, [p.seat for p in result.players], result.street, warnings
        ),
        player_states=states,
        history_complete=False,
        verified_for_statistics=False,
    )
    return result
