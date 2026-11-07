"""Serializable observations shared by recognition, tracking and capture storage."""

from dataclasses import asdict, dataclass


@dataclass
class PlayerObservation:
    roi: tuple[int, int, int, int]
    name: str
    confidence: float
    stack: str
    status: str
    raw_name: str = ""
    ocr_candidates: tuple = ()

    def to_dict(self):
        return asdict(self)


@dataclass
class CardObservation:
    zone: str
    roi: tuple[int, int, int, int]
    value: str
    confidence: float
    rank_confidence: float = 0.0
    suit_confidence: float = 0.0

    def to_dict(self):
        return asdict(self)
