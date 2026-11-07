from poker.hud.windows import outside_work_area


def test_recorded_window_overlaps_taskbar_by_29_pixels():
    assert outside_work_area((1202, 76, 1779, 1333), (0, 0, 3440, 1380)) == {
        "left": 0,
        "top": 0,
        "right": 0,
        "bottom": 29,
    }


def test_visible_window_and_negative_monitor_coordinates():
    assert not any(outside_work_area((-1900, 20, 1580, 1000), (-1920, 0, 0, 1040)).values())
    assert outside_work_area((-1940, -5, 2000, 1100), (-1920, 0, 0, 1040)) == {
        "left": 20,
        "top": 5,
        "right": 60,
        "bottom": 55,
    }
