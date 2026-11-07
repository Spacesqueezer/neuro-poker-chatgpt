"""Conservative identity tracking and explicit manual corrections."""

import math
from dataclasses import dataclass

from poker.hud.models import PlayerObservation


@dataclass
class Seat:
    key: int
    observation: PlayerObservation
    name: str = ""
    manual: bool = False
    candidate: str = ""
    confirmations: int = 0
    missing: int = 0
    conflict: bool = False
    manual_reference: str = ""
    display_roi: tuple = ()
    corroborations: int = 0


class TableState:
    def __init__(self, resolve_name=None):
        self.resolve_name = resolve_name or (lambda name: (name, False))
        self.seats: dict[int, Seat] = {}
        self.next_key = 1
        self.size = None

    def update(self, observations, size):
        if self.size and self.size != size:
            self.seats.clear()  # Never carry a position-bound identity across a new layout.
        self.size = size
        unused = set(self.seats)
        for observation in observations:
            x, y, w, _ = observation.roi
            closest = min(
                unused,
                key=lambda k: math.dist(self.seats[k].observation.roi[:2], (x, y)),
                default=None,
            )
            if (
                closest is None
                or math.dist(self.seats[closest].observation.roi[:2], (x, y)) > w * 0.5
            ):
                closest = self.next_key
                self.next_key += 1
                self.seats[closest] = Seat(closest, observation)
            unused.discard(closest)
            seat = self.seats[closest]
            if not seat.display_roi or any(
                abs(a - b) > max(4, w * 0.04)
                for a, b in zip(seat.display_roi, observation.roi, strict=True)
            ):
                seat.display_roi = observation.roi
            seat.observation, seat.missing = observation, 0
            name, corrected = self.resolve_name(observation.name)
            confidence = observation.confidence
            if confidence < 65:
                known = {}
                for text, score in observation.ocr_candidates:
                    resolved, explicit = self.resolve_name(text)
                    if explicit and score >= 65:
                        known.setdefault(resolved, []).append(score)
                supported = [
                    (resolved, min(scores))
                    for resolved, scores in known.items()
                    if len(scores) >= 2 and max(scores) >= 85
                ]
                if len(supported) == 1:
                    name, confidence = supported[0]
                    corrected = True
            if name:
                same_candidate = seat.candidate.casefold() == name.casefold()
                matching_views = sum(
                    text.casefold() == observation.name.casefold() and confidence >= 25
                    for text, confidence in observation.ocr_candidates
                )
                corroborated = observation.confidence >= 65 and matching_views >= 2
                seat.corroborations = (
                    seat.corroborations + 1
                    if corroborated and same_candidate
                    else 1
                    if corroborated
                    else 0
                )
                seat.confirmations = (
                    seat.confirmations + 1 if seat.candidate.casefold() == name.casefold() else 1
                )
                seat.candidate = name
                reference = (seat.manual_reference or seat.name) if seat.manual else seat.name
                reference = self.resolve_name(reference)[0]
                seat.conflict = bool(
                    reference
                    and name.casefold() not in {reference.casefold(), seat.name.casefold()}
                )
                # Dim plaques can produce a weak winning spelling even though
                # independent OCR views agree with the explicit manual identity.
                # Require exact evidence, never fuzzy-match a replacement player.
                manual_scores = [
                    confidence
                    for text, confidence in observation.ocr_candidates
                    if text.casefold() == seat.name.casefold() and confidence >= 65
                ]
                if (
                    seat.manual
                    and observation.confidence < 65
                    and len(manual_scores) >= 2
                    and max(manual_scores) >= 85
                ):
                    seat.conflict = False
                threshold = 90 if seat.name else 80
                if not seat.manual and (
                    (
                        seat.confirmations >= (4 if seat.name and seat.conflict else 2)
                        and observation.confidence >= threshold
                    )
                    or (not seat.name and seat.corroborations >= 4)
                ):
                    seat.name, seat.conflict = name, False
                if corrected and seat.confirmations >= 2 and confidence >= 65:
                    seat.name, seat.manual, seat.conflict = name, True, False
                    seat.manual_reference = name
            else:
                seat.corroborations = 0
            # Hidden action text does not erase the last confirmed identity.
        for key in unused:
            self.seats[key].corroborations = 0
            self.seats[key].missing += 1
            if self.seats[key].missing >= 10:
                del self.seats[key]
        return [seat for seat in self.seats.values() if not seat.missing]

    def correct(self, key, name):
        name = name.strip()
        if len(name) > 128:
            raise ValueError("Никнейм длиннее 128 символов")
        seat = self.seats[key]
        seat.name, seat.manual, seat.conflict = name, bool(name), False
        seat.manual_reference = seat.observation.name
        seat.candidate, seat.confirmations = "", 0
        seat.corroborations = 0
