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
	frozenset(("i", "l", "1")),
	frozenset(("o", "0")),
	frozenset(("s", "5")),
	frozenset(("b", "8")),
	frozenset(("g", "q")),
)

SAME_PLAYER_THRESHOLD = 0.78
CHANGE_CANDIDATE_THRESHOLD = 0.84
CHANGE_CONFIRMATIONS = 3
PERIODIC_NAME_RECHECK_SECONDS = 4.0
FINGERPRINT_CHANGE_THRESHOLD = 28.0
VISUAL_CHANGE_CONFIRMATIONS = 2
VISUAL_RETURN_CONFIRMATIONS = 2
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
		ratio = SequenceMatcher(
			None,
			left,
			right,
		).ratio()

		# Типичный OCR drift из captures:
		# bm51 -> obm51
		# dimitry -> dimitrvy
		# Одно вставленное/потерянное начертание не должно означать
		# "новый игрок", если остальная строка практически совпадает.
		length_delta = abs(
			len(left) - len(right)
		)

		if (
			length_delta == 1
			and ratio >= 0.80
		):
			return max(
				ratio,
				0.86,
			)

		return ratio

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
			maxlen=6
		)

		self.pending_name = ""
		self.change_pending = False
		self.visual_change_pending = False
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

			# Stable name не переписываем по каждому похожему OCR read.
			# Именно это вызывало "плавание" вроде:
			# dimitrvy -> dimitry -> dimitrvy
			# bm51 -> obm51 -> bm5t.
			#
			# Похожие чтения используются только как подтверждение
			# текущей личности. Исправить написание можно лишь через
			# отдельный сильный consensus ниже.
			recent = list(
				self.values
			)[-7:]

			candidate = _vote_strings(
				recent
			)

			if (
				candidate
				and candidate != self.stable_name
			):
				candidate_votes = sum(
					1
					for item in recent
					if item == candidate
				)

				stable_votes = sum(
					1
					for item in recent
					if item == self.stable_name
				)

				if (
					candidate_votes >= 5
					and candidate_votes
					> stable_votes + 2
					and _confusion_similarity(
						candidate,
						self.stable_name,
					) >= 0.88
				):
					self.stable_name = candidate

					self.values.clear()
					self.values.extend(
						[candidate] * 3
					)

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
		if len(self.values) < 3:
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

		if len(best) < 3:
			return ""

		return (
			_vote_strings(
				best
			)
			or best[-1]
		)

	def begin_visual_change(self):
		if not self.stable_name:
			return

		if self.visual_change_pending:
			return

		self.visual_change_pending = True
		self.pending_values.clear()
		self.pending_name = ""
		self.change_pending = False

	def cancel_visual_change(self):
		if not self.visual_change_pending:
			return

		self.visual_change_pending = False
		self.pending_values.clear()
		self.pending_name = ""
		self.change_pending = False

	def _observe_visual_candidate(
		self,
		value,
	):
		"""
		Сильное визуальное изменение nickname bitmap уже подтвердило,
		что в seat, вероятно, сидит другой человек.

		Пока visual pending активен, похожее на старый ник OCR-чтение
		НЕ имеет права вернуть старую identity. Это как раз лечит кейс:
		на экране уже `flesh1112`, а OCR ещё иногда выдаёт что-то,
		похожее на старый `teesallliz`.
		"""
		if not value:
			return "visual_pending"

		if (
			_confusion_similarity(
				value,
				self.stable_name,
			)
			>= SAME_PLAYER_THRESHOLD
		):
			return "visual_old_like"

		if (
			not self.pending_name
			or _confusion_similarity(
				value,
				self.pending_name,
			)
			< CHANGE_CANDIDATE_THRESHOLD
		):
			self.pending_values.clear()
			self.pending_values.append(
				value
			)
			self.pending_name = value

			return "visual_pending"

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
			return "visual_pending"

		self.stable_name = (
			self.pending_name
		)

		self.values.clear()
		self.values.extend(
			self.pending_values
		)

		self.visual_change_pending = False
		self._cancel_pending_change()
		self.changed_this_scan = True

		return "switched"

	def _observe_change_candidate(
		self,
		value,
	):
		if (
			not self.pending_name
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
			self.change_pending = False

			return "change_candidate"

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

		if confirmations >= 2:
			self.change_pending = True

		if confirmations < CHANGE_CONFIRMATIONS:
			return (
				"change_pending"
				if self.change_pending
				else "change_candidate"
			)

		self.stable_name = (
			self.pending_name
		)

		self.values.clear()
		self.values.extend(
			self.pending_values
		)

		self.visual_change_pending = False
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
		self._visual_change_hits = {}
		self._visual_return_hits = {}

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

				# Иногда action overlay не распознаётся action_reader,
				# но визуально он ярко-зелёный/оранжевый. Такой кадр
				# нельзя использовать ни для OCR ника, ни для fingerprint.
				if self._looks_like_action_overlay(
					name_frame
				):
					display_name = (
						history.display_name()
					)

					stable_name = (
						history.stable_name
					)

					hero_score = 0.0

					if stable_name:
						hero_score = (
							self._hero_similarity(
								stable_name
							)
						)

					players.append(
						DetectedPlayer(
							index=index,
							panel=panel,
							name=display_name,
							raw_name=(
								self._raw_cache.get(
									index,
									"",
								)
							),
							action=(
								action
								or "unknown"
							),
							hero_score=hero_score,
							confidence=history.confidence(),
							identity_pending=history.change_pending,
							identity_changed=False,
						)
					)

					if hero_score > best_score:
						best_score = hero_score
						best_index = index

					continue

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

				if changed_fingerprint:
					self._visual_change_hits[
						index
					] = min(
						3,
						self._visual_change_hits.get(
							index,
							0,
						)
						+ 1,
					)
				else:
					self._visual_change_hits[
						index
					] = 0

				self._visual_return_hits[
					index
				] = 0

				should_read = (
					not history.stable_name
					or history.change_pending
					or bool(
						history.pending_values
					)
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

					if raw_name == "*****":
						self._raw_cache[
							index
						] = raw_name

						continue

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
					should_store_fingerprint = (
						observation
						in {
							"stabilized",
							"switched",
						}
						or (
							observation == "same"
							and not changed_fingerprint
						)
					)

					if should_store_fingerprint:
						self._fingerprints[
							index
						] = fingerprint

						self._visual_change_hits[
							index
						] = 0

						self._visual_return_hits[
							index
						] = 0

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

			# HERO — особый случай.
			#
			# Для обычных игроков при pending identity мы специально
			# отдаём пустое имя: лучше временно "unknown", чем записать
			# нового человека в статистику старого.
			#
			# Но HERO известен из config и не должен исчезать из runtime
			# из-за одного плохого OCR. Пока новый ник не подтверждён
			# несколькими чтениями, держим стабильное имя HERO.
			stable_name = (
				history.stable_name
			)

			stable_hero_score = 0.0

			if stable_name:
				stable_hero_score = (
					self._hero_similarity(
						stable_name
					)
				)

			if (
				not display_name
				and stable_hero_score
				>= self.hero_threshold
			):
				display_name = (
					self.hero_name
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

	def _looks_like_action_overlay(
		self,
		image,
	):
		if (
			image is None
			or image.size == 0
		):
			return False

		hsv = cv2.cvtColor(
			image,
			cv2.COLOR_BGR2HSV,
		)

		saturation = hsv[:, :, 1]
		value = hsv[:, :, 2]

		colored = (
			(saturation >= 85)
			& (value >= 95)
		)

		colored_ratio = float(
			np.mean(
				colored
			)
		)

		return colored_ratio >= 0.055


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

		gray = cv2.GaussianBlur(
			gray,
			(3, 3),
			0,
		)

		_, mask = cv2.threshold(
			gray,
			0,
			255,
			cv2.THRESH_BINARY
			+ cv2.THRESH_OTSU,
		)

		# Верхняя кромка ROI и единичный anti-alias мусор не должны
		# влиять на identity fingerprint.
		mask[
			: min(
				2,
				mask.shape[0],
			),
			:
		] = 0

		count, labels, stats, _ = (
			cv2.connectedComponentsWithStats(
				mask,
				8,
			)
		)

		clean = np.zeros_like(
			mask
		)

		for component in range(
			1,
			count,
		):
			x, y, width, height, area = (
				stats[
					component
				]
			)

			if area < 4:
				continue

			if height < 3:
				continue

			clean[
				labels == component
			] = 255

		points = cv2.findNonZero(
			clean
		)

		if points is None:
			return None

		x, y, width, height = (
			cv2.boundingRect(
				points
			)
		)

		glyphs = clean[
			y:y + height,
			x:x + width,
		]

		canvas_width = 96
		canvas_height = 24
		padding = 2

		scale = min(
			(
				canvas_width
				- padding * 2
			)
			/ max(
				glyphs.shape[1],
				1,
			),
			(
				canvas_height
				- padding * 2
			)
			/ max(
				glyphs.shape[0],
				1,
			),
		)

		target_width = max(
			1,
			int(
				round(
					glyphs.shape[1]
					* scale
				)
			),
		)

		target_height = max(
			1,
			int(
				round(
					glyphs.shape[0]
					* scale
				)
			),
		)

		resized = cv2.resize(
			glyphs,
			(
				target_width,
				target_height,
			),
			interpolation=cv2.INTER_NEAREST,
		)

		canvas = np.zeros(
			(
				canvas_height,
				canvas_width,
			),
			dtype=np.uint8,
		)

		offset_x = (
			canvas_width
			- target_width
		) // 2

		offset_y = (
			canvas_height
			- target_height
		) // 2

		canvas[
			offset_y:
			offset_y + target_height,
			offset_x:
			offset_x + target_width,
		] = resized

		return canvas.astype(
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
			self._visual_change_hits.clear()
			self._visual_return_hits.clear()
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

				self._visual_change_hits[
					index
				] = 0

				self._visual_return_hits[
					index
				] = 0

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
		new_visual_change_hits = {}
		new_visual_return_hits = {}

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

				new_visual_change_hits[
					new_index
				] = self._visual_change_hits.get(
					old_index,
					0,
				)

				new_visual_return_hits[
					new_index
				] = self._visual_return_hits.get(
					old_index,
					0,
				)

			if old_index is None:
				new_visual_change_hits[
					new_index
				] = 0

				new_visual_return_hits[
					new_index
				] = 0

			new_centers[
				new_index
			] = panel.center

		self._histories = new_histories
		self._fingerprints = new_fingerprints
		self._raw_cache = new_raw_cache
		self._last_name_read_at = new_last_read
		self._panel_centers = new_centers
		self._visual_change_hits = new_visual_change_hits
		self._visual_return_hits = new_visual_return_hits

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
