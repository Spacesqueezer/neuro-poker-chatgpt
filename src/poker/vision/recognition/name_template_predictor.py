from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


LOWER_NAME_CHARS = (
	"abcdefghijklmnopqrstuvwxyz"
	"0123456789_-"
)


class CharacterTemplatePredictor:
	def __init__(
		self,
		project_root: Path,
	):
		self.project_root = project_root
		self.templates = {}
		self.reload()

	def reload(self):
		self.templates = {}

		root = (
			self.project_root
			/ "assets"
			/ "players"
			/ "templates"
			/ "chars"
		)

		if not root.exists():
			return

		for character in LOWER_NAME_CHARS:
			folder = root / character

			if not folder.exists():
				continue

			items = []

			for path in folder.glob(
				"*.png"
			):
				image = cv2.imread(
					str(path),
					cv2.IMREAD_GRAYSCALE,
				)

				if image is None:
					continue

				if image.shape != (
					40,
					28,
				):
					image = cv2.resize(
						image,
						(28, 40),
						interpolation=cv2.INTER_AREA,
					)

				items.append(
					image.astype(
						np.float32
					)
				)

			if items:
				self.templates[
					character
				] = items

	def predict(
		self,
		image,
	):
		if (
			image is None
			or image.size == 0
			or not self.templates
		):
			return (
				"",
				0.0,
			)

		if image.shape != (
			40,
			28,
		):
			image = cv2.resize(
				image,
				(28, 40),
				interpolation=cv2.INTER_AREA,
			)

		sample = image.astype(
			np.float32
		)

		best_character = ""
		best_score = 0.0

		for character, templates in (
			self.templates.items()
		):
			character_score = 0.0

			for template in templates:
				diff = np.mean(
					np.abs(
						sample
						- template
					)
				)

				score = max(
					0.0,
					1.0
					- diff / 255.0,
				)

				if score > character_score:
					character_score = score

			if character_score > best_score:
				best_score = character_score
				best_character = character

		return (
			best_character,
			best_score,
		)
