"""Coverage of visible street totals, not a fabricated accounting ledger."""

from copy import deepcopy

STREETS = ("preflop", "flop", "turn", "river")


def contribution_coverage(amounts, seats, street, warnings=()):
    """Only use the supplied causal fragment; never sum street maxima or deltas.

    A street transition does not prove the preceding last reading was final.
    Even an observed preflop total does not identify antes or forced payments.
    These gaps remain explicit until separate evidence can establish them.
    """
    expected = STREETS[: STREETS.index(street) + 1] if street in STREETS else ()
    all_seats = sorted(set(seats) | {a["seat"] for a in amounts})
    players = []
    for seat in all_seats:
        rows = []
        for name in expected:
            readings = [a for a in amounts if a["seat"] == seat and a["street"] == name]
            decreases = [
                a
                for a in readings
                if a["delta_since_previous_reading"] is not None
                and a["delta_since_previous_reading"] < 0
            ]
            reasons = ["street_opening_unverified"]
            if not readings:
                reasons.append("no_confirmed_amount")
            if name != street:
                reasons.append("street_final_unverified")
            if decreases:
                reasons.append("visible_amount_decreased")
            if warnings:
                reasons.append("hand_fragment_warnings")
            last = readings[-1] if readings else None
            rows.append(
                dict(
                    street=name,
                    observed_count=len(readings),
                    last_observed_total=last["visible_total"] if last else None,
                    last_observed_source=deepcopy(last["evidence"]) if last else None,
                    decrease_sources=[deepcopy(a["evidence"]) for a in decreases],
                    final_total=None,
                    blockers=reasons,
                )
            )
        players.append(
            dict(
                seat=seat,
                streets=rows,
                hand_contribution=None,
                blockers=["forced_contributions_unverified", "street_accounting_incomplete"],
            )
        )
    return dict(
        schema_version=1,
        semantics="coverage_only_not_training_labels",
        amounts_unit="observation_quantum",
        players=players,
        warnings=list(warnings),
        verified_for_statistics=False,
    )
