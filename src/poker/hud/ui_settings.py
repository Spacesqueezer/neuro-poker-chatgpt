"""Portable HUD appearance settings, independent of Tk."""

import json
import math


def load_settings(path):
    default = {"transparency": 25.0, "positions": {}, "auto_size_table": True, "hero_seat": 6}
    try:
        data = json.loads(path.read_text(encoding="utf8"))
        if type(data.get("auto_size_table")) is bool:
            default["auto_size_table"] = data["auto_size_table"]
        if type(data.get("hero_seat")) is int and 0 <= data["hero_seat"] <= 6:
            default["hero_seat"] = data["hero_seat"]
        value = float(data.get("transparency", 25))
        if math.isfinite(value):
            default["transparency"] = min(80, max(0, value))
        for key, xy in data.get("positions", {}).items():
            if len(xy) == 2 and all(type(v) in (float, int) and math.isfinite(v) for v in xy):
                default["positions"][str(key)] = [min(1, max(0, v)) for v in xy]
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return default


def save_settings(path, settings):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf8")
    temporary.replace(path)


def panel_position(normalized, size, panel_size):
    return tuple(
        round(min(1, max(0, value)) * max(0, total - panel))
        for value, total, panel in zip(normalized, size, panel_size, strict=True)
    )
