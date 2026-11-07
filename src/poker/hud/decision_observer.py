"""Diagnostic requests from the fast stream; no identity OCR, inference or database."""

from datetime import datetime

from poker.hud.advisor_state import build_advisor_draft
from poker.hud.decision_stream import proposal
from poker.hud.hand import HandObservation
from poker.hud.live_evidence import LiveEvidence

SOURCE_BLOCKERS = (
    "table_membership_unverified",
    "betting_state_unverified",
    "stacks_unverified",
    "turn_continuity_unverified",
)


def fast_decision_draft(context, source, facts, tracker, stream, *, latest_cards=None, now=None):
    """The caller validates capture epoch/window; never import older slow monetary facts."""
    if not facts or "decision_hand" not in context:
        stream.reset()
        return None
    hand = HandObservation(**context["decision_hand"])
    blockers = list(SOURCE_BLOCKERS)
    if latest_cards and (
        all(latest_cards.get(k) == source.get(k) for k in ("window", "evidence_epoch", "hero_seat"))
        and tuple(latest_cards.get("client_rect", [])) == tuple(source.get("client_rect", []))
        and datetime.fromisoformat(latest_cards["captured_at"])
        >= datetime.fromisoformat(source["captured_at"])
    ):
        current = latest_cards["hand"]
        if not current.get("my_turn"):
            stream.reset()
            return None
        if not current.get("valid") or any(
            list(current.get(k, [])) != list(getattr(hand, k)) for k in ("hero", "board")
        ):
            blockers.append("newer_cards_disagree")
    identity = context.get("hand_id", {})
    if facts.get("hand_id") is not None and facts["hand_id"] != identity.get("value"):
        stream.reset()
        return None
    draft = stream.update(
        LiveEvidence.apply(proposal(hand, (), context), facts),
        source,
        identity.get("value", "") if identity.get("confidence", 0) >= 80 else "",
        cards_valid=hand.valid,
        blockers=blockers,
        now=now,
    )
    if draft is None:
        return None
    # Names may remain empty: seats within the hand are the model identity.
    # UI nicknames and player statistics continue independently in the slow worker.
    return {
        **source,
        **draft,
        "decision_source": "fast_table",
        "model_called": False,
        "context": context,
        "live_evidence": facts,
        "advisor": build_advisor_draft(draft, tracker, source, context, facts),
        "players_evidence": [],
    }
