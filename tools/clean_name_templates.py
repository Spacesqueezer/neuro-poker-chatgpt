import argparse
import time

import cv2

from poker.vision.project_paths import find_project_root
from poker.vision.recognition.name_template_cleaner import (
	clean_character_template,
	clean_template_tree,
)


def _preview(project_root):
	template_root = (
		project_root
		/ "assets"
		/ "players"
		/ "templates"
		/ "chars"
	)

	samples = sorted(
		template_root.glob("*/*.png")
	)

	if not samples:
		print(
			"No character templates found."
		)
		return

	print(
		"Preview controls:"
	)
	print(
		"  Enter/Space = next"
	)
	print(
		"  Q = quit"
	)

	for path in samples:
		image = cv2.imread(
			str(path),
			cv2.IMREAD_GRAYSCALE,
		)

		result = clean_character_template(
			image
		)

		if result.cleaned is None:
			continue

		before = cv2.resize(
			image,
			None,
			fx=4.0,
			fy=4.0,
			interpolation=cv2.INTER_NEAREST,
		)

		after = cv2.resize(
			result.cleaned,
			None,
			fx=4.0,
			fy=4.0,
			interpolation=cv2.INTER_NEAREST,
		)

		cv2.imshow(
			"Before",
			before,
		)

		cv2.imshow(
			"After",
			after,
		)

		print(
			f"{path.parent.name}/{path.name}"
		)

		while True:
			key = cv2.waitKey(30) & 0xFF

			if key in (
				13,
				32,
			):
				break

			if key in (
				ord("q"),
				ord("Q"),
			):
				cv2.destroyAllWindows()
				return

			time.sleep(0.005)

	cv2.destroyAllWindows()


def main():
	parser = argparse.ArgumentParser(
		description=(
			"Clean character templates "
			"and move suspicious samples "
			"to rejected/."
		)
	)

	parser.add_argument(
		"--dry-run",
		action="store_true",
		help=(
			"Show statistics without "
			"changing files."
		),
	)

	parser.add_argument(
		"--preview",
		action="store_true",
		help=(
			"Preview before/after samples "
			"without changing files."
		),
	)

	args = parser.parse_args()
	project_root = find_project_root()

	if args.preview:
		_preview(
			project_root
		)
		return

	stats = clean_template_tree(
		project_root,
		dry_run=args.dry_run,
	)

	print(
		"Template cleanup complete:"
	)

	for key, value in stats.items():
		print(
			f"  {key}: {value}"
		)

	if args.dry_run:
		print(
			"Dry run: no files were changed."
		)
	else:
		print(
			"Rejected samples:"
		)
		print(
			project_root
			/ "assets"
			/ "players"
			/ "templates"
			/ "rejected"
		)


if __name__ == "__main__":
	main()
