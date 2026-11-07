from poker.hud.ui_settings import load_settings, panel_position, save_settings


def test_portable_positions_survive_restart_and_resize(tmp_path):
    path = tmp_path / "hud" / "ui.json"
    settings = {
        "transparency": 40.0,
        "positions": {"2": [0.5, 1.0]},
        "auto_size_table": False,
        "hero_seat": 4,
    }
    save_settings(path, settings)
    assert load_settings(path) == settings
    assert panel_position(settings["positions"]["2"], (1000, 600), (260, 100)) == (370, 500)
    assert panel_position(settings["positions"]["2"], (200, 80), (260, 100)) == (0, 0)


def test_damaged_or_out_of_bounds_settings_are_recoverable(tmp_path):
    path = tmp_path / "ui.json"
    assert load_settings(path)["transparency"] == 25
    path.write_text('{"transparency": 100, "positions": {"0": [-1, 3]}}')
    assert load_settings(path) == {
        "transparency": 80,
        "positions": {"0": [0, 1]},
        "auto_size_table": True,
        "hero_seat": 6,
    }
    path.write_text("broken")
    assert load_settings(path) == {
        "transparency": 25,
        "positions": {},
        "auto_size_table": True,
        "hero_seat": 6,
    }
