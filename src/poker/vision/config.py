import json
from pathlib import Path


def load_vision_config(path="vision_config.json"):
	with open(path, "r", encoding="utf-8") as file:
		return json.load(file)
