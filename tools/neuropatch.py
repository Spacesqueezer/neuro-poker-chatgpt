#!/usr/bin/env python3
"""
NeuroPatch v3.1

Transaction patch engine:
- validation
- external transaction storage
- git safety check
- backups
- rollback
- dry run
- reports
- history
- optional auto commit
"""

import argparse
import datetime
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
PATCH_DIR = Path.home() / "Downloads"

NEUROPATCH_HOME = Path.home() / ".neuropatch" / PROJECT_ROOT.name
TRANSACTION_DIR = NEUROPATCH_HOME / "transactions"
HISTORY_FILE = NEUROPATCH_HOME / "history.json"
APPLIED_PATCH_DIR = PROJECT_ROOT / "patches" / "applied"
AI_WORK_BRANCH = "ai-development"


class PatchError(Exception):
	pass


def read_json(path):
	return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, data):
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(
		json.dumps(data, indent=2, ensure_ascii=False),
		encoding="utf-8"
	)


def play_result_sound(success):
	if sys.platform != "win32":
		return

	filename = (
		"alarm_success.mp3"
		if success
		else "alarm_error.mp3"
	)
	path = PROJECT_ROOT / "sound" / filename

	if not path.exists():
		return

	player_code = """
import ctypes
import sys

path = sys.argv[1]
alias = "neuropatch_result"
winmm = ctypes.windll.winmm

if winmm.mciSendStringW(
	f'open "{path}" type mpegvideo alias {alias}',
	None,
	0,
	None,
) != 0:
	raise SystemExit(0)

try:
	winmm.mciSendStringW(
		f"setaudio {alias} volume to 1000",
		None,
		0,
		None,
	)
	winmm.mciSendStringW(
		f"play {alias} wait",
		None,
		0,
		None,
	)
finally:
	winmm.mciSendStringW(
		f"close {alias}",
		None,
		0,
		None,
	)
"""

	try:
		subprocess.Popen(
			[sys.executable, "-c", player_code, str(path)],
			stdin=subprocess.DEVNULL,
			stdout=subprocess.DEVNULL,
			stderr=subprocess.DEVNULL,
			creationflags=(
				subprocess.DETACHED_PROCESS
				| subprocess.CREATE_NO_WINDOW
			),
			close_fds=True,
		)
	except Exception:
		return


def git_status():
	result = subprocess.run(
		["git", "status", "--short"],
		cwd=PROJECT_ROOT,
		text=True,
		capture_output=True
	)
	return result.stdout.strip()


def git_current_branch():
	result = subprocess.run(
		["git", "branch", "--show-current"],
		cwd=PROJECT_ROOT,
		text=True,
		capture_output=True,
		check=True,
	)
	return result.stdout.strip()


def git_local_branch_exists(branch):
	result = subprocess.run(
		[
			"git",
			"show-ref",
			"--verify",
			"--quiet",
			f"refs/heads/{branch}",
		],
		cwd=PROJECT_ROOT,
	)
	return result.returncode == 0


def git_branch_has_upstream(branch):
	result = subprocess.run(
		[
			"git",
			"rev-parse",
			"--abbrev-ref",
			f"{branch}@{{upstream}}",
		],
		cwd=PROJECT_ROOT,
		text=True,
		capture_output=True,
	)
	return result.returncode == 0


def ensure_ai_work_branch():
	current = git_current_branch()

	if current != AI_WORK_BRANCH:
		command = ["git", "switch", AI_WORK_BRANCH]
		if not git_local_branch_exists(AI_WORK_BRANCH):
			command = ["git", "switch", "-c", AI_WORK_BRANCH]

		subprocess.run(
			command,
			cwd=PROJECT_ROOT,
			check=True,
		)

	if not git_branch_has_upstream(AI_WORK_BRANCH):
		subprocess.run(
			[
				"git",
				"push",
				"--set-upstream",
				"origin",
				AI_WORK_BRANCH,
			],
			cwd=PROJECT_ROOT,
			check=True,
		)

	return AI_WORK_BRANCH


def git_commit(message):
	subprocess.run(
		["git", "add", "."],
		cwd=PROJECT_ROOT,
		check=True
	)

	subprocess.run(
		["git", "commit", "-m", message],
		cwd=PROJECT_ROOT,
		check=True
	)

	result = subprocess.run(
		["git", "rev-parse", "HEAD"],
		cwd=PROJECT_ROOT,
		text=True,
		capture_output=True,
		check=True
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


def stage_successful_patch_archive(patch_path, patch_id):
	APPLIED_PATCH_DIR.mkdir(parents=True, exist_ok=True)
	target = APPLIED_PATCH_DIR / f"{patch_id}.npatch.json"

	if target.exists():
		raise PatchError(
			f"Archived patch already exists: {target.relative_to(PROJECT_ROOT)}"
		)

	shutil.copy2(patch_path, target)
	return target


def remove_staged_patch_archive(path):
	if path is not None and path.exists():
		path.unlink()


def cleanup_downloaded_patch(patch_path):
	try:
		patch_path.unlink(missing_ok=True)
		return None
	except OSError as error:
		return str(error)


def load_history():
	if not HISTORY_FILE.exists():
		return []

	return read_json(HISTORY_FILE)


def create_transaction(patch_id):
	path = TRANSACTION_DIR / patch_id
	path.mkdir(parents=True, exist_ok=True)
	return path


def backup_files(transaction, operations):
	created = []

	for operation in operations:
		file = PROJECT_ROOT / operation["file"]

		if operation["type"] == "create_file":
			created.append(operation["file"])
			continue

		if file.exists():
			target = transaction / "before" / operation["file"]
			target.parent.mkdir(parents=True, exist_ok=True)
			shutil.copy2(file, target)

	save_json(transaction / "created.json", created)


def rollback(transaction):
	source = transaction / "before"

	if source.exists():
		for file in source.rglob("*"):
			if file.is_file():
				target = PROJECT_ROOT / file.relative_to(source)
				target.parent.mkdir(parents=True, exist_ok=True)
				shutil.copy2(file, target)

	created_file = transaction / "created.json"

	if created_file.exists():
		for file in read_json(created_file):
			target = PROJECT_ROOT / file
			if target.exists():
				target.unlink()


def validate_patch(patch):
	for key in ["patch_id", "goal", "operations"]:
		if key not in patch:
			raise PatchError(f"Missing {key}")


def check_allowed_files(patch):
	allowed = patch.get("allowed_files")

	if not allowed:
		return

	for operation in patch["operations"]:
		if operation["file"] not in allowed:
			raise PatchError(f"File not allowed: {operation['file']}")


def apply_operation(operation):
	target = PROJECT_ROOT / operation["file"]

	if operation["type"] == "create_file":
		if target.exists():
			raise PatchError(f"File already exists: {operation['file']}")

		target.parent.mkdir(parents=True, exist_ok=True)
		target.write_text(
			operation["content"],
			encoding="utf-8"
		)

	elif operation["type"] == "replace":
		if not target.exists():
			raise PatchError(f"Missing file: {operation['file']}")

		old = target.read_text(encoding="utf-8")

		if old.count(operation["old"]) != 1:
			raise PatchError(f"Replace mismatch: {operation['file']}")

		target.write_text(
			old.replace(operation["old"], operation["new"], 1),
			encoding="utf-8"
		)

	elif operation["type"] == "delete_file":
		target.unlink(missing_ok=True)

	else:
		raise PatchError(f"Unsupported operation: {operation['type']}")


def run_tests(patch):
	for command in patch.get("validation", {}).get("commands", []):
		result = subprocess.run(
			command,
			shell=True,
			cwd=PROJECT_ROOT
		)

		if result.returncode:
			raise PatchError(f"Test failed: {command}")


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--dry-run", action="store_true")
	parser.add_argument("--force", action="store_true")
	args = parser.parse_args()

	patch_path = load_patch()
	patch = read_json(patch_path)

	validate_patch(patch)
	check_allowed_files(patch)

	if git_status() and not args.force:
		raise PatchError("Git working tree dirty. Commit changes or use --force.")

	branch = git_current_branch()
	if not args.dry_run:
		branch = ensure_ai_work_branch()

	transaction = create_transaction(patch["patch_id"])
	started_monotonic = time.perf_counter()

	report = {
		"patch": patch["patch_id"],
		"started": datetime.datetime.now().isoformat(),
		"status": "FAILED",
		"transaction": str(transaction),
		"branch": branch,
	}
	archived_patch = None

	try:
		if not args.dry_run:
			backup_files(transaction, patch["operations"])

			for operation in patch["operations"]:
				apply_operation(operation)

			run_tests(patch)

			archived_patch = stage_successful_patch_archive(
				patch_path,
				patch["patch_id"],
			)

			history = load_history()
			history.append(
				{
					"patch_id": patch["patch_id"],
					"time": datetime.datetime.now().isoformat()
				}
			)

			save_json(HISTORY_FILE, history)

			commit_hash = None

			if patch.get("git", {}).get("auto_commit", True):
				commit_hash = git_commit(f"[auto-patch] {patch['patch_id']}")
				report["commit"] = commit_hash
				report["archived_patch"] = str(
					archived_patch.relative_to(PROJECT_ROOT)
				)
				cleanup_warning = cleanup_downloaded_patch(
					patch_path
				)
				if cleanup_warning is not None:
					report["patch_cleanup_warning"] = cleanup_warning

		report["status"] = "SUCCESS"

	except Exception as error:
		rollback(transaction)
		remove_staged_patch_archive(archived_patch)
		report["error"] = str(error)

	finally:
		report["duration_seconds"] = round(
			time.perf_counter() - started_monotonic,
			3,
		)
		save_json(transaction / "report.json", report)

		print(json.dumps(report, indent=2, ensure_ascii=False))
		if report["status"] == "SUCCESS":
			print(
				"SUCCESS HANDOFF: commit pushed on ai-development. "
				"Inspect the fresh repository branch ai-development, "
				"re-read docs/DEV_RULES.md and docs/PROJECT_STATE.md, "
				"follow the recorded next step, and return the next "
				".npatch.json file immediately."
			)
		play_result_sound(
			report["status"] == "SUCCESS"
		)


if __name__ == "__main__":
	try:
		main()
	except Exception:
		play_result_sound(False)
		raise
