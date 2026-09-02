from pathlib import Path
import json
import shutil

import cv2

from poker.vision.project_paths import find_project_root
from poker.vision.recognition.name_character_templates import (
	save_character_template,
	segment_known_name,
)


TARGETS = {"_", "-"}


def main():
	project_root = find_project_root()

	template_root = (
		project_root
		/ "assets"
		/ "players"
		/ "templates"
		/ "chars"
	)

	archive_root = (
		project_root
		/ "assets"
		/ "players"
		/ "templates"
		/ "rejected"
		/ "legacy_positionless"
	)

	for character in TARGETS:
		source = template_root / character

		if source.exists():
			target = archive_root / character

			if target.exists():
				shutil.rmtree(target)

			target.parent.mkdir(
				parents=True,
				exist_ok=True,
			)

			shutil.move(
				str(source),
				str(target),
			)

			print(
				f"Archived old '{character}' templates -> {target}"
			)

	state_path = (
		project_root
		/ "captures"
		/ "name_labeler_state.json"
	)

	if not state_path.exists():
		print(
			"No name_labeler_state.json. Re-label new samples with _ or -."
		)
		return

	state = json.loads(
		state_path.read_text(
			encoding="utf-8"
		)
	)

	recovered = {
		"_": 0,
		"-": 0,
	}

	for relative_path, record in state.get("samples", {}).items():
		if record.get("status") != "accepted":
			continue

		nickname = record.get("nickname", "")

		if not any(
			character in nickname
			for character in TARGETS
		):
			continue

		path = project_root / relative_path
		image = cv2.imread(str(path))

		if image is None:
			continue

		crop = record.get("crop")

		if isinstance(crop, list) and len(crop) == 4:
			x1, y1, x2, y2 = [
				int(value)
				for value in crop
			]

			image = image[
				y1:y2,
				x1:x2,
			]

		segmented = segment_known_name(
			project_root,
			image,
			nickname,
		)

		if segmented is None:
			continue

		for character, segment in zip(
			nickname,
			segmented.segments,
		):
			if character not in TARGETS:
				continue

			save_character_template(
				project_root,
				character,
				segment,
			)

			recovered[character] += 1

	print("Rebuild complete:")

	for character in ("_", "-"):
		print(
			f"  {character}: {recovered[character]} samples"
		)


if __name__ == "__main__":
	main()
