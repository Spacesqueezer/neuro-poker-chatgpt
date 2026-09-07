\
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re
import threading
import time

from poker.vision.project_paths import find_project_root


_VALID_NAME_RE = re.compile(
	r"^[a-z0-9_]{3,32}$"
)


@dataclass(frozen=True)
class ManualIdentity:
	seat_index: int
	name: str
	confirmed_at: float
	source: str = "manual"


class ManualIdentityRegistry:
	def __init__(self):
		self._lock = threading.RLock()
		self._by_seat = {}

	def normalize(
		self,
		value,
	):
		value = (
			str(
				value or ""
			)
			.strip()
			.lower()
		)

		value = re.sub(
			r"[^a-z0-9_]",
			"",
			value,
		)

		return value

	def set(
		self,
		seat_index,
		name,
	):
		normalized = self.normalize(
			name
		)

		if not _VALID_NAME_RE.fullmatch(
			normalized
		):
			raise ValueError(
				"Nickname must contain only "
				"a-z, 0-9 and underscore "
				"(3-32 chars)."
			)

		identity = ManualIdentity(
			seat_index=int(
				seat_index
			),
			name=normalized,
			confirmed_at=time.time(),
		)

		with self._lock:
			self._by_seat[
				identity.seat_index
			] = identity

		self._append_audit(
			"set",
			identity,
		)

		return identity

	def get(
		self,
		seat_index,
	):
		with self._lock:
			return self._by_seat.get(
				int(
					seat_index
				)
			)

	def clear(
		self,
		seat_index,
		reason="",
	):
		seat_index = int(
			seat_index
		)

		with self._lock:
			identity = self._by_seat.pop(
				seat_index,
				None,
			)

		if identity is not None:
			self._append_audit(
				"clear",
				identity,
				reason=reason,
			)

		return identity

	def clear_all(
		self,
		reason="",
	):
		with self._lock:
			items = list(
				self._by_seat.values()
			)
			self._by_seat.clear()

		for identity in items:
			self._append_audit(
				"clear",
				identity,
				reason=reason,
			)

	def snapshot(self):
		with self._lock:
			return dict(
				self._by_seat
			)

	def _append_audit(
		self,
		event,
		identity,
		reason="",
	):
		try:
			project_root = (
				find_project_root()
			)

			path = (
				project_root
				/ "samples"
				/ "manual_name_corrections.jsonl"
			)

			path.parent.mkdir(
				parents=True,
				exist_ok=True,
			)

			record = {
				"event": event,
				"seat_index": (
					identity.seat_index
				),
				"name": identity.name,
				"timestamp": time.time(),
				"reason": reason,
			}

			with path.open(
				"a",
				encoding="utf-8",
			) as stream:
				stream.write(
					json.dumps(
						record,
						ensure_ascii=False,
					)
					+ "\n"
				)
		except Exception:
			# HUD must never be able to break Vision.
			pass


MANUAL_IDENTITIES = (
	ManualIdentityRegistry()
)
