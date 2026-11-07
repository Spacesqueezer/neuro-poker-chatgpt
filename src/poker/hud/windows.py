"""Small typed Win32 boundary; coordinates are physical client-area pixels."""

import ctypes as c
import os
from ctypes import wintypes as w
from dataclasses import dataclass


@dataclass(frozen=True)
class Window:
    handle: int
    title: str
    rect: tuple[int, int, int, int]


class MonitorInfo(c.Structure):
    _fields_ = [("size", w.DWORD), ("monitor", w.RECT), ("work", w.RECT), ("flags", w.DWORD)]


def outside_work_area(rect, work):
    """Return overflow in physical pixels; work uses Win32 left/top/right/bottom."""
    x, y, width, height = rect
    left, top, right, bottom = work
    return {
        "left": max(0, left - x),
        "top": max(0, top - y),
        "right": max(0, x + width - right),
        "bottom": max(0, y + height - bottom),
    }


def recommended_window_rect(client, outer, work):
    """Keep aspect ratio and existing larger tables; fit including window borders."""
    x, y, width, height = client
    ox, oy, ow, oh = outer
    left, top, right, bottom = work
    border_w, border_h = max(0, ow - width), max(0, oh - height)
    available_w = right - left - 32 - border_w
    available_h = bottom - top - 32 - border_h
    if available_w < 400 or available_h < 300:
        return None
    scale = min(max(1, 1280 / width), available_w / width, available_h / height)
    nw, nh = round(width * scale) + border_w, round(height * scale) + border_h
    return (
        max(left + 16, min(ox, right - 16 - nw)),
        max(top + 16, min(oy, bottom - 16 - nh)),
        nw,
        nh,
    )


class Desktop:
    def __init__(self):
        self.api = c.WinDLL("user32", use_last_error=True)
        self.callback_type = c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
        declarations = {
            "EnumWindows": ([self.callback_type, w.LPARAM], w.BOOL),
            "IsWindowVisible": ([w.HWND], w.BOOL),
            "IsIconic": ([w.HWND], w.BOOL),
            "IsZoomed": ([w.HWND], w.BOOL),
            "GetWindowRect": ([w.HWND, c.POINTER(w.RECT)], w.BOOL),
            "GetWindowTextLengthW": ([w.HWND], c.c_int),
            "GetWindowTextW": ([w.HWND, w.LPWSTR, c.c_int], c.c_int),
            "GetClientRect": ([w.HWND, c.POINTER(w.RECT)], w.BOOL),
            "ClientToScreen": ([w.HWND, c.POINTER(w.POINT)], w.BOOL),
            "GetAncestor": ([w.HWND, w.UINT], w.HWND),
            "GetForegroundWindow": ([], w.HWND),
            "GetAsyncKeyState": ([c.c_int], w.SHORT),
            "GetCursorPos": ([c.POINTER(w.POINT)], w.BOOL),
            "GetWindow": ([w.HWND, w.UINT], w.HWND),
            "GetWindowThreadProcessId": ([w.HWND, c.POINTER(w.DWORD)], w.DWORD),
            "GetWindowLongPtrW": ([w.HWND, c.c_int], c.c_ssize_t),
            "SetWindowLongPtrW": ([w.HWND, c.c_int, c.c_ssize_t], c.c_ssize_t),
            "SetWindowDisplayAffinity": ([w.HWND, w.DWORD], w.BOOL),
            "SetWindowPos": ([w.HWND, w.HWND, c.c_int, c.c_int, c.c_int, c.c_int, w.UINT], w.BOOL),
            "SetProcessDpiAwarenessContext": ([c.c_void_p], w.BOOL),
            "MonitorFromWindow": ([w.HWND, w.DWORD], w.HANDLE),
            "GetMonitorInfoW": ([w.HANDLE, c.POINTER(MonitorInfo)], w.BOOL),
        }
        for name, (args, result) in declarations.items():
            function = getattr(self.api, name)
            function.argtypes, function.restype = args, result
        self.api.SetProcessDpiAwarenessContext(c.c_void_p(-4))

    def work_area(self, handle):
        monitor = self.api.MonitorFromWindow(handle, 2)
        info = MonitorInfo()
        info.size = c.sizeof(info)
        if monitor and self.api.GetMonitorInfoW(monitor, c.byref(info)):
            return [info.work.left, info.work.top, info.work.right, info.work.bottom]
        return None

    def fit_table(self, handle):
        before = self.rect(handle)
        work = self.work_area(handle)
        if not before or not work or self.api.IsZoomed(handle):
            return {"status": "skipped", "before": before, "reason": "unavailable_or_maximized"}
        bounds = w.RECT()
        if not self.api.GetWindowRect(handle, c.byref(bounds)):
            raise c.WinError(c.get_last_error())
        outer = (bounds.left, bounds.top, bounds.right - bounds.left, bounds.bottom - bounds.top)
        target = recommended_window_rect(before, outer, work)
        if target is None:
            return {"status": "skipped", "before": before, "reason": "work_area_too_small"}
        # SWP_NOZORDER | SWP_NOACTIVATE: no focus stealing or topmost changes.
        if target != outer and not self.api.SetWindowPos(handle, None, *target, 0x14):
            raise c.WinError(c.get_last_error())
        return {
            "status": "applied",
            "before": before,
            "requested_outer": target,
            "after": self.rect(handle),
            "work_area": work,
        }

    def rect(self, handle):
        if not self.api.IsWindowVisible(handle) or self.api.IsIconic(handle):
            return None
        rect, point = w.RECT(), w.POINT(0, 0)
        if not self.api.GetClientRect(handle, c.byref(rect)) or not self.api.ClientToScreen(
            handle, c.byref(point)
        ):
            return None
        if rect.right < 400 or rect.bottom < 300:
            return None
        return point.x, point.y, rect.right, rect.bottom

    def title(self, handle: int) -> str | None:
        """Read current title; the selected Window.title is only a stable label."""
        length = self.api.GetWindowTextLengthW(handle)
        if length <= 0 or length > 4096:
            return None
        title = c.create_unicode_buffer(length + 1)
        return title.value if self.api.GetWindowTextW(handle, title, length + 1) > 0 else None

    def windows(self):
        result = []

        def collect(handle, _):
            process = w.DWORD()
            self.api.GetWindowThreadProcessId(handle, c.byref(process))
            rect = self.rect(handle)
            if rect and process.value != os.getpid():
                title = self.title(handle)
                if title:
                    result.append(Window(handle, title, rect))
            return True

        self.api.EnumWindows(self.callback_type(collect), 0)
        return sorted(result, key=lambda item: ("pokerdom" not in item.title.lower(), item.title))

    def own_foreground(self, target):
        foreground = self.api.GetForegroundWindow()
        if foreground == target:
            return True
        process = w.DWORD()
        self.api.GetWindowThreadProcessId(foreground, c.byref(process))
        if process.value != os.getpid():
            return False
        target_rect = self.rect(target)
        if not target_rect:
            return False
        # Clicking the HUD must not authorize capturing an unrelated application
        # that currently covers the selected table underneath it.
        cursor = self.api.GetWindow(foreground, 2)  # GW_HWNDNEXT: next lower in Z order.
        visited = set()
        while cursor and cursor not in visited:
            if cursor == target:
                return True
            visited.add(cursor)
            self.api.GetWindowThreadProcessId(cursor, c.byref(process))
            rect = self.rect(cursor)
            if rect and process.value != os.getpid():
                x, y, width, height = rect
                tx, ty, tw, th = target_rect
                if x < tx + tw and x + width > tx and y < ty + th and y + height > ty:
                    return False
            cursor = self.api.GetWindow(cursor, 2)
        return False

    def configure_overlay(self, widget, click_through=False):
        widget.update_idletasks()
        handle = self.api.GetAncestor(widget.winfo_id(), 2)
        if click_through:
            style = self.api.GetWindowLongPtrW(handle, -20)
            self.api.SetWindowLongPtrW(handle, -20, style | 0x80000 | 0x20 | 0x08000000)
        return bool(self.api.SetWindowDisplayAffinity(handle, 0x11))

    def position(self, widget, x, y, width, height):
        # Tk geometry '-x' is an offset from the right edge, not a negative
        # desktop coordinate. SetWindowPos also supports monitors left of primary.
        widget.update_idletasks()
        handle = self.api.GetAncestor(widget.winfo_id(), 2)
        if not self.api.SetWindowPos(handle, w.HWND(-1), x, y, width, height, 0x10):
            raise c.WinError(c.get_last_error())

    def mouse_sample(self, target):
        """Only buttons inside the foreground target; no keyboard or global log."""
        down = tuple(bool(self.api.GetAsyncKeyState(key) & 0x8000) for key in (1, 2))
        if self.api.GetForegroundWindow() != target:
            return down, None
        rect = self.rect(target)
        point = w.POINT()
        if not rect or not self.api.GetCursorPos(c.byref(point)):
            return down, None
        x, y, width, height = rect
        px, py = point.x - x, point.y - y
        if 0 <= px < width and 0 <= py < height:
            return down, {
                "position": [px, py],
                "norm": [px / width, py / height],
                "client_rect": rect,
            }
        return down, None
