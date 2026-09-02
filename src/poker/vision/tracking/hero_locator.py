from dataclasses import dataclass
from difflib import SequenceMatcher
import threading
import time

from poker.vision.ocr.name_reader import read_player_name


@dataclass
class HeroSnapshot:
	seat: str | None = None
	name: str | None = None
	score: float = 0.0
	updated_at: float = 0.0
	players: dict[str, str] | None = None


class HeroLocator:
	def __init__(self, hero_name, min_score=0.72):
		self.hero_name = hero_name.lower()
		self.min_score = min_score
		self._lock = threading.Lock()
		self._snapshot = HeroSnapshot(players={})

	def scan(self, table_frame, seat_rois):
		players = {}
		best_seat = None
		best_name = None
		best_score = 0.0

		for seat_name, rois in seat_rois.items():
			x1, y1, x2, y2 = rois["name"]
			crop = table_frame[y1:y2, x1:x2]

			if crop.size == 0:
				players[seat_name] = ""
				continue

			name = read_player_name(crop)
			players[seat_name] = name

			if not name:
				continue

			score = SequenceMatcher(
				None,
				name.lower(),
				self.hero_name,
			).ratio()

			if score > best_score:
				best_score = score
				best_seat = seat_name
				best_name = name

		now = time.time()

		with self._lock:
			if best_seat is not None and best_score >= self.min_score:
				self._snapshot = HeroSnapshot(
					seat=best_seat,
					name=best_name,
					score=best_score,
					updated_at=now,
					players=players,
				)
			else:
				current = self._snapshot

				# Keep the last confirmed seat while OCR is temporarily obscured.
				if current.seat is not None and now - current.updated_at <= 5.0:
					self._snapshot = HeroSnapshot(
						seat=current.seat,
						name=current.name,
						score=current.score,
						updated_at=current.updated_at,
						players=players,
					)
				else:
					self._snapshot = HeroSnapshot(
						players=players,
					)

	def get_snapshot(self):
		with self._lock:
			current = self._snapshot

			return HeroSnapshot(
				seat=current.seat,
				name=current.name,
				score=current.score,
				updated_at=current.updated_at,
				players=dict(current.players or {}),
			)
