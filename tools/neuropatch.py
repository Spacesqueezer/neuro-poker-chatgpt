#!/usr/bin/env python3

"""
NeuroPatch v2.2

Transaction engine:
- preflight validation
- full backup before apply
- atomic-ish apply flow
- automatic rollback on failure
- transaction reports
- history only after success
"""

import argparse
import datetime
import difflib
import json
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
PATCH_DIR = Path.home() / "Downloads"

DATA_DIR = PROJECT_ROOT / ".neuropatch"
TRANSACTION_DIR = DATA_DIR / "transactions"
HISTORY_FILE = DATA_DIR / "history.json"


class PatchError(Exception):
	pass


def read_json(path):
	return json.loads(
		path.read_text(
			encoding="utf-8"
		)
	)


def save_json(path, data):
	path.parent.mkdir(
		parents=True,
		exist_ok=True
	)

	path.write_text(
		json.dumps(
			data,
			indent=2,
			ensure_ascii=False
		),
		encoding="utf-8"
	)


def git_status():
	result = subprocess.run(
		["git", "status", "--short"],
		cwd=PROJECT_ROOT,
		text=True,
		capture_output=True
	)

	return result.stdout.strip()


def load_patch():
	patches = sorted(
		PATCH_DIR.glob("*.npatch.json"),
		key=lambda item: item.stat().st_mtime,
		reverse=True
	)

	if not patches:
		raise PatchError("No patch found")

	return patches[0]


def load_history():
	if not HISTORY_FILE.exists():
		return []

	return read_json(HISTORY_FILE)


def create_transaction(patch_id):
	path = TRANSACTION_DIR / patch_id

	path.mkdir(
		parents=True,
		exist_ok=True
	)

	return path


def backup_files(transaction, operations):
	for operation in operations:
		file = PROJECT_ROOT / operation["file"]

		if file.exists():
			target = transaction / "before" / operation["file"]
			target.parent.mkdir(
				parents=True,
				exist_ok=True
			)

			shutil.copy2(
				file,
				target
			)


def rollback(transaction):
	source = transaction / "before"

	if not source.exists():
		return

	for file in source.rglob("*"):
		if file.is_file():
			target = PROJECT_ROOT / file.relative_to(source)
			target.parent.mkdir(
				parents=True,
				exist_ok=True
			)

			shutil.copy2(
				file,
				target
			)


def validate_patch(patch):
	for key in ["patch_id", "goal", "operations"]:
		if key not in patch:
			raise PatchError(
				f"Missing {key}"
			)


def check_allowed_files(patch):
	allowed = patch.get("allowed_files")

	if not allowed:
		return

	for operation in patch["operations"]:
		if operation["file"] not in allowed:
			raise PatchError(
				f"File not allowed: {operation['file']}"
			)


def apply_operation(operation):
	target = PROJECT_ROOT / operation["file"]

	if operation["type"] == "create_file":
		target.parent.mkdir(
			parents=True,
			exist_ok=True
		)

		target.write_text(
			operation["content"],
			encoding="utf-8"
		)

	elif operation["type"] == "replace":
		old = target.read_text(
			encoding="utf-8"
		)

		if old.count(operation["old"]) != 1:
			raise PatchError(
				f"Replace mismatch: {operation['file']}"
			)

		target.write_text(
			old.replace(
				operation["old"],
				operation["new"],
				1
			),
			encoding="utf-8"
		)

	elif operation["type"] == "delete_file":
		target.unlink(
			missing_ok=True
		)

	else:
		raise PatchError(
			f"Unsupported operation: {operation['type']}"
		)


def run_tests(patch):
	for command in patch.get("validation", {}).get("commands", []):
		result = subprocess.run(
			command,
			shell=True,
			cwd=PROJECT_ROOT
		)

		if result.returncode:
			raise PatchError(
				f"Test failed: {command}"
			)


def main():
	parser = argparse.ArgumentParser()

	parser.add_argument(
		"--dry-run",
		action="store_true"
	)

	args = parser.parse_args()

	patch = read_json(
		load_patch()
	)

	validate_patch(patch)
	check_allowed_files(patch)

	transaction = create_transaction(
		patch["patch_id"]
	)

	report = {
		"patch": patch["patch_id"],
		"started": datetime.datetime.now().isoformat(),
		"status": "FAILED"
	}

	try:
		if not args.dry_run:
			backup_files(
				transaction,
				patch["operations"]
			)

			for operation in patch["operations"]:
				apply_operation(operation)

			run_tests(
				patch
			)

			history = load_history()
			history.append(
				{
					"patch_id": patch["patch_id"],
					"time": datetime.datetime.now().isoformat()
				}
			)

			save_json(
				HISTORY_FILE,
				history
			)

		report["status"] = "SUCCESS"

	except Exception as error:
		rollback(transaction)
		report["error"] = str(error)

	finally:
		save_json(
			transaction / "report.json",
			report
		)

		print(
			json.dumps(
				report,
				indent=2,
				ensure_ascii=False
			)
		)


if __name__ == "__main__":
	main()
