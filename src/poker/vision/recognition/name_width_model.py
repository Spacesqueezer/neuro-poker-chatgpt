from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import math

import cv2
import numpy as np


DEFAULT_WIDTHS = {
	"i": 0.38,
	"l": 0.42,
	"j": 0.46,
	"t": 0.52,
	"f": 0.54,
	"r": 0.56,
	"1": 0.58,
	"I": 0.58,
	"m": 1.08,
	"w": 1.04,
	"M": 1.10,
	"W": 1.12,
	"0": 0.78,
	"8": 0.78,
	"9": 0.76,
	"6": 0.76,
	"5": 0.72,
	"2": 0.72,
	"3": 0.72,
	"4": 0.74,
	"7": 0.68,
	"_": 0.74,
	"-": 0.62,
}


@dataclass(frozen=True)
class WidthModel:
	values: dict[str, float]

	def get(self, character: str) -> float:
		if character in self.values:
			return float(self.values[character])

		if character in DEFAULT_WIDTHS:
			return float(DEFAULT_WIDTHS[character])

		if character.isupper():
			return 0.78

		if character.isdigit():
			return 0.74

		return 0.70


def load_width_model(project_root: Path) -> WidthModel:
	path = (
		project_root
		/ "assets"
		/ "players"
		/ "templates"
		/ "width_model.json"
	)

	values = {}

	if path.exists():
		try:
			values = json.loads(
				path.read_text(
					encoding="utf-8"
				)
			)
		except Exception:
			values = {}

	return WidthModel(
		values=values
	)


def save_width_model(
	project_root: Path,
	model: WidthModel,
):
	path = (
		project_root
		/ "assets"
		/ "players"
		/ "templates"
		/ "width_model.json"
	)

	path.parent.mkdir(
		parents=True,
		exist_ok=True,
	)

	path.write_text(
		json.dumps(
			model.values,
			ensure_ascii=False,
			indent=2,
			sort_keys=True,
		),
		encoding="utf-8",
	)


def expected_boundaries(
	label: str,
	model: WidthModel,
	total_width: int,
) -> list[float]:
	weights = [
		model.get(character)
		for character in label
	]

	total = sum(weights)

	if total <= 0:
		return []

	result = []
	running = 0.0

	for weight in weights[:-1]:
		running += weight
		result.append(
			total_width
			* running
			/ total
		)

	return result


def update_width_model(
	project_root: Path,
	label: str,
	segment_widths: list[int],
	learning_rate: float = 0.18,
):
	if not label:
		return

	if len(label) != len(segment_widths):
		return

	mean_width = (
		sum(segment_widths)
		/ max(
			len(segment_widths),
			1,
		)
	)

	if mean_width <= 0:
		return

	model = load_width_model(
		project_root
	)

	values = dict(
		model.values
	)

	for character, width in zip(
		label,
		segment_widths,
	):
		relative = (
			width
			/ mean_width
		)

		old = values.get(
			character,
			DEFAULT_WIDTHS.get(
				character,
				0.70,
			),
		)

		values[character] = (
			old * (1.0 - learning_rate)
			+ relative * learning_rate
		)

	save_width_model(
		project_root,
		WidthModel(
			values=values
		),
	)
