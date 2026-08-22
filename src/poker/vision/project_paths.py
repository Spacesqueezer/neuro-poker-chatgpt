from pathlib import Path


def find_project_root():
	current = Path(__file__).resolve()

	for parent in current.parents:
		if (parent / "assets").exists() and (parent / "src").exists():
			return parent

	raise RuntimeError("Could not find project root")


def get_assets_path():
	return find_project_root() / "assets"
