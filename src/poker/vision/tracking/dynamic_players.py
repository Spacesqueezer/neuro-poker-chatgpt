from collections import Counter, deque
from dataclasses import dataclass
from difflib import SequenceMatcher
import re
import time

import cv2
import numpy as np

from poker.vision.detection.player_panels import (
	crop_name_from_panel,
	crop_panel,
)
from poker.vision.ocr.action_reader import read_player_action
from poker.vision.ocr.name_reader import read_player_name


CONFUSION_GROUPS = (
	frozenset(("y", "v")),
)

SAME_PLAYER_THRESHOLD = 0.82
CHANGE_CANDIDATE_THRESHOLD = 0.82
CHANGE_CONFIRMATIONS = 2
PERIODIC_NAME_RECHECK_SECONDS = 4.0
FINGERPRINT_CHANGE_THRESHOLD = 10.0
PANEL_MATCH_DISTANCE_FACTOR = 0.90


@dataclass
class DetectedPlayer:
	index: int
	panel: object
	name: str = ""
	raw_name: str = ""
	action: str | None = None
	is_hero: bool = False
	hero_score: float = 0.0
	confidence: float = 0.0
	identity_pending: bool = False
	identity_changed: bool = False


def _confusion_equal(
	left,
	right,
):
	if left == right:
		return True

	for group in CONFUSION_GROUPS:
		if (
			left in group
			and right in group
		):
			return True

	return False


def _confusion_similarity(
	left,
	right,
):
	if not left or not right:
		return 0.0

	if len(left) != len(right):
		return SequenceMatcher(
			None,
			left,
			right,
		).ratio()

	matches = 0.0

	for left_char, right_char in zip(
		left,
		right,
	):
		if left_char == right_char:
			matches += 1.0
		elif _confusion_equal(
			left_char,
			right_char,
		):
			matches += 0.82

	return matches / len(left)


def _vote_strings(
	values,
):
	values = [
		value
		for value in values
		if value
	]

	if not values:
		return ""

	length_counts = Counter(
		len(value)
		for value in values
	)

	best_length = (
		length_counts
		.most_common(1)[0][0]
	)

	values = [
		value
		for value in values
		if len(value) == best_length
	]

	if not values:
		return ""

	result = []

	for index in range(
		best_length
	):
		chars = Counter(
			value[index]
			for value in values
		)

		character = (
			chars
			.most_common(1)[0][0]
		)

		result.append(
			character
		)

	return "".join(result)


class NameHistory:
	"""
	История именно личности игрока в одном физическом seat.

	Ключевое правило:
	как только появился убедительный другой ник, старый stable_name
	НЕЛЬЗЯ продолжать отдавать наружу. Пока смена не подтверждена,
	seat считается identity_pending и name наружу становится пустым.

	Это специально консервативно: для сбора статистики кратковременно
	"не знаю игрока" безопаснее, чем несколько рук писать действия
	нового человека в статистику старого.
	"""

	def __init__(
		self,
		maxlen=9,
	):
		self.values = deque(
			maxlen=maxlen
		)

		self.stable_name = ""

		self.pending_values = deque(
			maxlen=4
		)

		self.pending_name = ""
		self.change_pending = False
		self.changed_this_scan = False

	def observe(
		self,
		value,
	):
		self.changed_this_scan = False

		if not value:
			return "empty"

		if not self.stable_name:
			self.values.append(
				value
			)

			candidate = self._initial_candidate()

			if candidate:
				self.stable_name = candidate

				self.values.clear()
				self.values.append(
					candidate
				)

				return "stabilized"

			return "warming"

		similarity = _confusion_similarity(
			value,
			self.stable_name,
		)

		if similarity >= SAME_PLAYER_THRESHOLD:
			self._cancel_pending_change()

			self.values.append(
				value
			)

			# Не дёргаем stable_name на каждом OCR-варианте.
			# Но если последние чтения согласованно дают чуть лучшее
			# написание того же ника, разрешаем мягкое уточнение.
			recent = list(
				self.values
			)[-5:]

			candidate = _vote_strings(
				recent
			)

			if (
				candidate
				and _confusion_similarity(
					candidate,
					self.stable_name,
				) >= 0.94
			):
				self.stable_name = candidate

			return "same"

		return self._observe_change_candidate(
			value
		)

	def display_name(self):
		if self.change_pending:
			return ""

		return self.stable_name

	def confidence(self):
		if (
			self.change_pending
			or not self.stable_name
			or not self.values
		):
			return 0.0

		votes = sum(
			1
			for value in self.values
			if _confusion_similarity(
				value,
				self.stable_name,
			) >= SAME_PLAYER_THRESHOLD
		)

		return votes / len(
			self.values
		)

	def _initial_candidate(self):
		if len(self.values) < 2:
			return ""

		values = list(
			self.values
		)

		clusters = []

		for value in values:
			placed = False

			for cluster in clusters:
				if _confusion_similarity(
					value,
					cluster[0],
				) >= SAME_PLAYER_THRESHOLD:
					cluster.append(
						value
					)

					placed = True
					break

			if not placed:
				clusters.append(
					[value]
				)

		clusters.sort(
			key=len,
			reverse=True,
		)

		best = clusters[0]

		if len(best) < 2:
			return ""

		return (
			_vote_strings(
				best
			)
			or best[-1]
		)

	def _observe_change_candidate(
		self,
		value,
	):
		if (
			not self.change_pending
			or not self.pending_name
			or _confusion_similarity(
				value,
				self.pending_name,
			) < CHANGE_CANDIDATE_THRESHOLD
		):
			self.pending_values.clear()

			self.pending_values.append(
				value
			)

			self.pending_name = value
			self.change_pending = True

			return "change_pending"

		self.pending_values.append(
			value
		)

		self.pending_name = (
			_vote_strings(
				self.pending_values
			)
			or value
		)

		confirmations = sum(
			1
			for candidate
			in self.pending_values
			if _confusion_similarity(
				candidate,
				self.pending_name,
			) >= CHANGE_CANDIDATE_THRESHOLD
		)

		if confirmations < CHANGE_CONFIRMATIONS:
			return "change_pending"

		self.stable_name = (
			self.pending_name
		)

		self.values.clear()
		self.values.extend(
			self.pending_values
		)

		self._cancel_pending_change()
		self.changed_this_scan = True

		return "switched"

	def _cancel_pending_change(self):
		self.pending_values.clear()
		self.pending_name = ""
		self.change_pending = False


class DynamicPlayerTracker:
	def __init__(
		self,
		hero_name,
		hero_threshold=0.72,
	):
		self.hero_name = self._normalize_name(
			hero_name
		)

		self.hero_threshold = hero_threshold
		self.players = []
		self.last_scan = 0.0

		self._histories = {}
		self._fingerprints = {}
		self._raw_cache = {}
		self._last_name_read_at = {}
		self._panel_centers = {}

	def update_ocr(
		self,
		table_frame,
		panels,
	):
		players = []
		best_index = None
		best_score = 0.0
		now = time.monotonic()

		self._sync_state(
			panels
		)

		for index, panel in enumerate(
			panels
		):
			panel_frame = crop_panel(
				table_frame,
				panel,
			)

			action = read_player_action(
				panel_frame
			)

			history = self._histories[
				index
			]

			raw_name = ""

			if action is None:
				name_frame = crop_name_from_panel(
					panel_frame
				)

				fingerprint = self._fingerprint(
					name_frame
				)

				last_read = (
					self._last_name_read_at
					.get(
						index,
						0.0,
					)
				)

				periodic_recheck = (
					now - last_read
					>= PERIODIC_NAME_RECHECK_SECONDS
				)

				changed_fingerprint = (
					self._fingerprint_changed(
						index,
						fingerprint,
					)
				)

				should_read = (
					not history.stable_name
					or history.change_pending
					or changed_fingerprint
					or periodic_recheck
				)

				if should_read:
					try:
						raw_name = read_player_name(
							name_frame
						).strip()
					except Exception as error:
						print(
							f"[OCR] Player {index}: "
							f"{error}"
						)

					self._last_name_read_at[
						index
					] = now

					normalized = self._normalize_name(
						raw_name
					)

					observation = "empty"

					if len(normalized) >= 3:
						observation = history.observe(
							normalized
						)

					# ВАЖНО:
					# fingerprint хранится как baseline текущей
					# подтверждённой личности. При подозрении на смену
					# мы его НЕ заменяем новым изображением.
					#
					# Поэтому новый ник продолжит считаться изменением
					# на следующих OCR-циклах и быстро получит второе
					# подтверждение, вместо того чтобы залипнуть на
					# старом stable_name на несколько рук.
					if observation in {
						"same",
						"stabilized",
						"switched",
					}:
						self._fingerprints[
							index
						] = fingerprint

					self._raw_cache[
						index
					] = raw_name
				else:
					raw_name = (
						self._raw_cache.get(
							index,
							"",
						)
					)

			display_name = (
				history.display_name()
			)

			hero_score = 0.0

			if display_name:
				hero_score = (
					self._hero_similarity(
						display_name
					)
				)

			if hero_score > best_score:
				best_score = hero_score
				best_index = index

			players.append(
				DetectedPlayer(
					index=index,
					panel=panel,
					name=display_name,
					raw_name=raw_name,
					action=action,
					hero_score=hero_score,
					confidence=history.confidence(),
					identity_pending=history.change_pending,
					identity_changed=history.changed_this_scan,
				)
			)

		if (
			best_index is not None
			and best_score
			>= self.hero_threshold
		):
			players[
				best_index
			].is_hero = True

			players[
				best_index
			].name = self.hero_name

		self._remove_duplicate_names(
			players
		)

		self.players = players
		self.last_scan = now

		return players

	def _remove_duplicate_names(
		self,
		players,
	):
		by_name = {}

		for player in players:
			if not player.name:
				continue

			by_name.setdefault(
				player.name,
				[],
			).append(
				player
			)

		for name, duplicates in (
			by_name.items()
		):
			if len(duplicates) <= 1:
				continue

			duplicates.sort(
				key=lambda player: (
					1
					if player.is_hero
					else 0,
					player.confidence,
					len(
						player.raw_name
						or ""
					),
				),
				reverse=True,
			)

			for duplicate in (
				duplicates[1:]
			):
				duplicate.name = ""
				duplicate.confidence = 0.0

	def _fingerprint(
		self,
		image,
	):
		if (
			image is None
			or image.size == 0
		):
			return None

		gray = cv2.cvtColor(
			image,
			cv2.COLOR_BGR2GRAY,
		)

		# Убираем часть влияния общей яркости white/gray nickname.
		gray = cv2.normalize(
			gray,
			None,
			0,
			255,
			cv2.NORM_MINMAX,
		)

		small = cv2.resize(
			gray,
			(40, 12),
			interpolation=cv2.INTER_AREA,
		)

		return small.astype(
			np.int16
		)

	def _fingerprint_changed(
		self,
		index,
		current,
	):
		if current is None:
			return False

		previous = (
			self._fingerprints.get(
				index
			)
		)

		if previous is None:
			return True

		if (
			previous.shape
			!= current.shape
		):
			return True

		diff = np.mean(
			np.abs(
				previous
				- current
			)
		)

		return (
			diff
			>= FINGERPRINT_CHANGE_THRESHOLD
		)

	def _sync_state(
		self,
		panels,
	):
		"""
		Переназначает state по физической позиции panel, а не слепо
		по номеру в sorted list.

		Это защищает от ещё одного опасного сценария:
		если число найденных игроков изменилось, clockwise index может
		сдвинуться и history одного seat окажется у соседнего игрока.
		"""

		if not panels:
			self._histories.clear()
			self._fingerprints.clear()
			self._raw_cache.clear()
			self._last_name_read_at.clear()
			self._panel_centers.clear()
			return

		if not self._panel_centers:
			for index, panel in enumerate(
				panels
			):
				self._histories[
					index
				] = NameHistory()

				self._panel_centers[
					index
				] = panel.center

			return

		old_indices = list(
			self._panel_centers.keys()
		)

		pairs = []

		for new_index, panel in enumerate(
			panels
		):
			new_center = panel.center

			for old_index in old_indices:
				old_center = (
					self._panel_centers[
						old_index
					]
				)

				distance = float(
					np.hypot(
						new_center[0]
						- old_center[0],
						new_center[1]
						- old_center[1],
					)
				)

				max_distance = max(
					30.0,
					float(
						panel.width
					)
					* PANEL_MATCH_DISTANCE_FACTOR,
				)

				if distance <= max_distance:
					pairs.append(
						(
							distance,
							new_index,
							old_index,
						)
					)

		pairs.sort(
			key=lambda item: item[0]
		)

		new_to_old = {}
		used_old = set()

		for (
			distance,
			new_index,
			old_index,
		) in pairs:
			if new_index in new_to_old:
				continue

			if old_index in used_old:
				continue

			new_to_old[
				new_index
			] = old_index

			used_old.add(
				old_index
			)

		new_histories = {}
		new_fingerprints = {}
		new_raw_cache = {}
		new_last_read = {}
		new_centers = {}

		for new_index, panel in enumerate(
			panels
		):
			old_index = (
				new_to_old.get(
					new_index
				)
			)

			if old_index is None:
				new_histories[
					new_index
				] = NameHistory()
			else:
				new_histories[
					new_index
				] = self._histories.get(
					old_index,
					NameHistory(),
				)

				if old_index in self._fingerprints:
					new_fingerprints[
						new_index
					] = self._fingerprints[
						old_index
					]

				if old_index in self._raw_cache:
					new_raw_cache[
						new_index
					] = self._raw_cache[
						old_index
					]

				if old_index in self._last_name_read_at:
					new_last_read[
						new_index
					] = self._last_name_read_at[
						old_index
					]

			new_centers[
				new_index
			] = panel.center

		self._histories = new_histories
		self._fingerprints = new_fingerprints
		self._raw_cache = new_raw_cache
		self._last_name_read_at = new_last_read
		self._panel_centers = new_centers

	def _normalize_name(
		self,
		value,
	):
		if not value:
			return ""

		value = (
			value
			.strip()
			.lower()
		)

		value = re.sub(
			r"^[^a-z0-9]+",
			"",
			value,
		)

		value = re.sub(
			r"[^a-z0-9]+$",
			"",
			value,
		)

		value = re.sub(
			r"[^a-z0-9_-]",
			"",
			value,
		)

		return value.strip(
			"_-"
		)

	def _hero_similarity(
		self,
		value,
	):
		if not value:
			return 0.0

		return max(
			_confusion_similarity(
				value,
				self.hero_name,
			),
			SequenceMatcher(
				None,
				value,
				self.hero_name,
			).ratio(),
		)
