from types import SimpleNamespace

from poker.hud.windows import Desktop, recommended_window_rect


def test_table_grows_preserving_ratio_and_borders():
    result = recommended_window_rect(
        (108, 130, 1000, 800), (100, 100, 1016, 838), (0, 0, 3440, 1380)
    )
    assert result == (100, 100, 1296, 1062)


def test_table_fits_negative_monitor_and_taskbar():
    result = recommended_window_rect(
        (-1000, 100, 1096, 890), (-1008, 70, 1112, 928), (-1920, 0, 0, 1040)
    )
    x, y, width, height = result
    assert x >= -1904 and x + width <= -16
    assert y >= 16 and y + height <= 1024
    assert abs((width - 16) / (height - 38) - 1096 / 890) < 0.002


def test_larger_table_stays_larger_and_tiny_work_area_is_skipped():
    rect = (100, 100, 1400, 1000)
    assert recommended_window_rect(rect, rect, (0, 0, 3440, 1380)) == rect
    assert recommended_window_rect(rect, rect, (0, 0, 300, 200)) is None


def test_resize_keeps_focus_and_skips_maximized_window():
    desktop = object.__new__(Desktop)
    calls = []

    def bounds(handle, pointer):
        rect = pointer._obj
        rect.left, rect.top, rect.right, rect.bottom = 100, 100, 1116, 938
        return True

    desktop.rect = lambda handle: (108, 130, 1000, 800)
    desktop.work_area = lambda handle: (0, 0, 3440, 1380)
    desktop.api = SimpleNamespace(
        IsZoomed=lambda handle: False,
        GetWindowRect=bounds,
        SetWindowPos=lambda *args: calls.append(args) or True,
    )
    assert desktop.fit_table(123)["status"] == "applied"
    assert calls == [(123, None, 100, 100, 1296, 1062, 0x14)]
    desktop.api.IsZoomed = lambda handle: True
    assert desktop.fit_table(123)["status"] == "skipped"
    assert len(calls) == 1
