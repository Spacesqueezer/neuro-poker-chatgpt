from poker.vision.hud.runtime_patch import (
	install_overlay_runtime,
)


def run():
	install_overlay_runtime()

	from poker.vision.runner import run as vision_run

	vision_run()


if __name__ == "__main__":
	run()
