"""Offline time-window associations, never action sizing or training labels."""

from collections import Counter
from datetime import datetime, timedelta


def _timing(amount, actions):
    """Include retrospective street confirmation, not just the caption timestamp."""
    sources = [amount, *actions]
    evidence = [
        frame
        for source in sources
        for key in ("confirmation_frames", "street_confirmation_frames")
        for frame in source.get(key, [])
    ]
    last = max(datetime.fromisoformat(s["captured_at"]) for s in sources + evidence)
    action_at = datetime.fromisoformat(actions[0]["captured_at"]) if len(actions) == 1 else None
    return {
        "last_evidence_captured_at": last.isoformat(),
        "capture_span_after_action_ms": (
            (last - action_at) // timedelta(milliseconds=1) if action_at else None
        ),
        "uses_evidence_after_action": last > action_at if action_at else None,
        "processing_latency_ms": None,
    }


def associate_bets(hands, max_seconds=3):
    results = []
    for hand in hands:
        actions = [
            e
            for e in hand["events"]
            if e["kind"] == "action_label" and e["action"] in {"bet", "call", "raise"}
        ]
        amounts = [e for e in hand["events"] if e["kind"] == "bet_amount" and e["value"] > 0]
        candidates = []
        for amount in amounts:
            first = (amount.get("confirmation_frames") or [amount])[0]
            at = datetime.fromisoformat(first["captured_at"])
            candidates.append(
                [
                    i
                    for i, action in enumerate(actions)
                    if amount.get("street") is not None
                    and action.get("street") == amount["street"]
                    and action["seat_index"] == amount["seat_index"]
                    and abs((datetime.fromisoformat(action["captured_at"]) - at).total_seconds())
                    <= max_seconds
                ]
            )
        # A caption can appear after the stake changed. Preserve the symmetric
        # associations, but separately identify observations starting at/after
        # the caption. This is capture order, never proof of causality.
        post_caption = []
        relations = []
        for amount, indices in zip(amounts, candidates, strict=True):
            frames = amount.get("confirmation_frames") or [amount]
            start = min(datetime.fromisoformat(f["captured_at"]) for f in frames)
            end = max(datetime.fromisoformat(f["captured_at"]) for f in frames)
            group, labels = [], []
            for i in indices:
                at = datetime.fromisoformat(actions[i]["captured_at"])
                relation = (
                    "before_caption"
                    if end < at
                    else "at_or_after_caption"
                    if start >= at
                    else "straddles_caption"
                )
                labels.append(relation)
                if relation == "at_or_after_caption":
                    group.append(i)
            post_caption.append(group)
            relations.append(labels)
        post_uses = Counter(i for group in post_caption for i in group)
        uses = Counter(i for group in candidates for i in group)
        for amount, indices, post, labels in zip(
            amounts, candidates, post_caption, relations, strict=True
        ):
            unique = len(indices) == 1 and uses[indices[0]] == 1
            linked_actions = [actions[i] for i in indices]
            timing = _timing(amount, linked_actions)
            results.append(
                {
                    "schema_version": 1,
                    "hand_id": hand["hand_id"],
                    "seat_index": amount["seat_index"],
                    "street": amount.get("street"),
                    "status": "unique_candidate"
                    if unique
                    else "ambiguous"
                    if indices
                    else "unmatched",
                    "amount_observation": amount,
                    "action_candidates": linked_actions,
                    "confirmation_timing": timing,
                    "candidate_capture_relations": labels,
                    "post_caption_action_candidates": [actions[i] for i in post],
                    "post_caption_status": (
                        "unique_candidate"
                        if len(post) == 1 and post_uses[post[0]] == 1
                        else "ambiguous"
                        if post
                        else "none"
                    ),
                    "capture_order_proves_action_amount": False,
                    "uses_later_evidence": (
                        datetime.fromisoformat(timing["last_evidence_captured_at"])
                        > datetime.fromisoformat(amount["captured_at"])
                    ),
                    "amount_semantics": "visible_total_not_action_size",
                    "verified_for_statistics": False,
                }
            )
    return results
