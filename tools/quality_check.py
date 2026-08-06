import subprocess

commands = [
	"ruff check .",
	"ruff format --check .",
	"pyright",
	"pytest --cov",
]

for command in commands:
	result = subprocess.run(command, shell=True)

	if result.returncode != 0:
		raise SystemExit(result.returncode)
