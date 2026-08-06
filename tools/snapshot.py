#!/usr/bin/env python3

"""
NeuroPatch AI Snapshot Creator v3.2
"""

import datetime
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path


TOOLS_DIR = Path(__file__).parent
PROJECT_ROOT = TOOLS_DIR.parent
SNAPSHOT_DIR = TOOLS_DIR / "snapshots"

MAX_SNAPSHOTS = 5


EXCLUDED_DIRS = {
	".git",
	".venv",
	"venv",
	"__pycache__",
	".idea",
	".vscode",
	".pytest_cache",
	".mypy_cache",
	".ruff_cache",
	"node_modules",
	"dist",
	"build",
	"cache",
	"logs",
	"artifacts",
	"datasets",
	"dataset",
	"models",
	"weights",
	"checkpoints",
	"neuropatch_data",
	"snapshots",
	".ai"
}


EXCLUDED_FILES = {
	".DS_Store",
	"reqs.txt",
	"requirements.txt"
}


EXCLUDED_EXTENSIONS = {
	".pyc",
	".pyo",
	".pt",
	".pth",
	".onnx",
	".bin"
}


def should_include(path):
	if any(part in EXCLUDED_DIRS for part in path.parts):
		return False

	if path.name in EXCLUDED_FILES:
		return False

	if path.suffix in EXCLUDED_EXTENSIONS:
		return False

	if path.suffix == ".log":
		return False

	return True


def sha256_file(path):
	hash_value = hashlib.sha256()

	with path.open("rb") as file:
		for chunk in iter(lambda: file.read(1024 * 1024), b""):
			hash_value.update(chunk)

	return hash_value.hexdigest()


def run_git(args):
	try:
		return subprocess.check_output(
			["git"] + args,
			cwd=PROJECT_ROOT,
			text=True,
			stderr=subprocess.DEVNULL
		).strip()
	except Exception:
		return None


def collect_files():
	return [
		path
		for path in PROJECT_ROOT.rglob("*")
		if path.is_file() and should_include(path)
	]


def collect_ai_context(archive):
	ai_folder = PROJECT_ROOT / ".ai"

	if not ai_folder.exists():
		return

	for file in ai_folder.rglob("*"):
		if file.is_file():
			archive.write(
				file,
				Path("ai_context") / file.relative_to(ai_folder)
			)


def build_tree():
	lines = [PROJECT_ROOT.name]

	def walk(folder, prefix=""):
		items = sorted(
			[item for item in folder.iterdir() if should_include(item)],
			key=lambda item: (item.is_file(), item.name.lower())
		)

		for index, item in enumerate(items):
			last = index == len(items) - 1

			lines.append(
				prefix + ("└── " if last else "├── ") + item.name
			)

			if item.is_dir():
				walk(
					item,
					prefix + ("    " if last else "│   ")
				)

	walk(PROJECT_ROOT)
	return "\n".join(lines)


def create_manifest(files):
	return [
		{
			"path": str(file.relative_to(PROJECT_ROOT)),
			"size": file.stat().st_size,
			"sha256": sha256_file(file)
		}
		for file in files
	]


def create_analysis():
	entrypoints = []

	for file in PROJECT_ROOT.rglob("*.py"):
		if not should_include(file):
			continue

		if file.name in {
			"main.py",
			"run.py",
			"app.py",
			"evaluate.py",
			"evaluate_arena.py"
		}:
			entrypoints.append(str(file.relative_to(PROJECT_ROOT)))

	return f"""# Project Analysis

Project:
{PROJECT_ROOT.name}

Language:
Python

Package manager:
pyproject.toml

Entrypoints:
{chr(10).join(entrypoints) if entrypoints else "Not detected"}

AI Context:
available

Tests:
{"detected" if (PROJECT_ROOT / "tests").exists() else "not detected"}
"""


def cleanup_old_snapshots():
	files = sorted(
		SNAPSHOT_DIR.glob("project_snapshot_*.zip"),
		key=lambda item: item.stat().st_mtime,
		reverse=True
	)

	for old in files[MAX_SNAPSHOTS:]:
		old.unlink()


def main():
	SNAPSHOT_DIR.mkdir(exist_ok=True)

	target = SNAPSHOT_DIR / (
		"project_snapshot_"
		+ datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
		+ ".zip"
	)

	files = collect_files()

	with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
		for file in files:
			archive.write(
				file,
				Path("project") / file.relative_to(PROJECT_ROOT)
			)

		collect_ai_context(archive)

		archive.writestr(
			"metadata/structure.txt",
			build_tree()
		)

		archive.writestr(
			"metadata/project_analysis.md",
			create_analysis()
		)

		archive.writestr(
			"metadata/snapshot_manifest.json",
			json.dumps(
				create_manifest(files),
				indent=2,
				ensure_ascii=False
			)
		)

		archive.writestr(
			"metadata/git_info.json",
			json.dumps(
				{
					"branch": run_git(["branch", "--show-current"]),
					"commit": run_git(["rev-parse", "HEAD"]),
					"dirty": bool(run_git(["status", "--short"])),
					"status": run_git(["status", "--short"])
				},
				indent=2,
				ensure_ascii=False
			)
		)

	cleanup_old_snapshots()

	print(target)


if __name__ == "__main__":
	main()
