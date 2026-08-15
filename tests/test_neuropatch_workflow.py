import tools.neuropatch as neuropatch


def test_successful_patch_archive_stages_copy_without_deleting_source(
	tmp_path,
	monkeypatch,
):
	downloads = tmp_path / "Downloads"
	downloads.mkdir()
	patch_path = downloads / "example.npatch.json"
	patch_path.write_text('{"patch_id":"example"}', encoding="utf-8")
	archive_dir = tmp_path / "repo" / "patches" / "applied"
	monkeypatch.setattr(
		neuropatch,
		"APPLIED_PATCH_DIR",
		archive_dir,
	)

	target = neuropatch.stage_successful_patch_archive(
		patch_path,
		"example",
	)

	assert patch_path.exists()
	assert target == archive_dir / "example.npatch.json"
	assert target.read_text(encoding="utf-8") == patch_path.read_text(
		encoding="utf-8"
	)


def test_cleanup_downloaded_patch_removes_successful_source(tmp_path):
	patch_path = tmp_path / "example.npatch.json"
	patch_path.write_text("{}", encoding="utf-8")

	warning = neuropatch.cleanup_downloaded_patch(patch_path)

	assert warning is None
	assert not patch_path.exists()


def test_ensure_ai_work_branch_creates_and_publishes_new_branch(
	monkeypatch,
):
	commands = []

	monkeypatch.setattr(
		neuropatch,
		"git_current_branch",
		lambda: "main",
	)
	monkeypatch.setattr(
		neuropatch,
		"git_local_branch_exists",
		lambda branch: False,
	)
	monkeypatch.setattr(
		neuropatch,
		"git_branch_has_upstream",
		lambda branch: False,
	)

	def fake_run(command, **kwargs):
		commands.append(command)

		class Result:
			returncode = 0

		return Result()

	monkeypatch.setattr(neuropatch.subprocess, "run", fake_run)

	branch = neuropatch.ensure_ai_work_branch()

	assert branch == "ai-development"
	assert commands == [
		["git", "switch", "-c", "ai-development"],
		[
			"git",
			"push",
			"--set-upstream",
			"origin",
			"ai-development",
		],
	]


def test_replace_mismatch_reports_operation_index_and_preview(
	tmp_path,
	monkeypatch,
):
	project_root = tmp_path / "repo"
	project_root.mkdir()
	target = project_root / "sample.txt"
	target.write_text("actual text\n", encoding="utf-8")
	monkeypatch.setattr(neuropatch, "PROJECT_ROOT", project_root)

	operation = {
		"type": "replace",
		"file": "sample.txt",
		"old": "expected\ntext",
		"new": "replacement",
	}

	try:
		neuropatch.apply_operation(operation, operation_index=7)
	except neuropatch.PatchError as error:
		message = str(error)
		assert "operation=7" in message
		assert "file=sample.txt" in message
		assert "matches=0" in message
		assert "old_preview=" in message
		assert "expected" in message
		assert "text" in message
	else:
		raise AssertionError("replace mismatch must raise PatchError")


def test_git_push_pushes_named_branch_to_origin(monkeypatch):
	commands = []

	def fake_run(command, **kwargs):
		commands.append((command, kwargs))

		class Result:
			returncode = 0

		return Result()

	monkeypatch.setattr(neuropatch.subprocess, "run", fake_run)

	neuropatch.git_push("ai-development")

	assert commands == [
		(
			["git", "push", "origin", "ai-development"],
			{
				"cwd": neuropatch.PROJECT_ROOT,
				"check": True,
			},
		),
	]


def test_ensure_ai_work_branch_reuses_existing_upstream_branch(
	monkeypatch,
):
	commands = []

	monkeypatch.setattr(
		neuropatch,
		"git_current_branch",
		lambda: "main",
	)
	monkeypatch.setattr(
		neuropatch,
		"git_local_branch_exists",
		lambda branch: True,
	)
	monkeypatch.setattr(
		neuropatch,
		"git_branch_has_upstream",
		lambda branch: True,
	)

	def fake_run(command, **kwargs):
		commands.append(command)

		class Result:
			returncode = 0

		return Result()

	monkeypatch.setattr(neuropatch.subprocess, "run", fake_run)

	branch = neuropatch.ensure_ai_work_branch()

	assert branch == "ai-development"
	assert commands == [
		["git", "switch", "ai-development"],
	]
