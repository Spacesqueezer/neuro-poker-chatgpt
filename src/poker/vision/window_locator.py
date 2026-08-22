import win32gui


def find_pokerdom_window():
	result = []

	def callback(hwnd, _):
		if not win32gui.IsWindowVisible(hwnd):
			return

		title = win32gui.GetWindowText(hwnd)

		if "PokerDom" in title or "Pokerdom" in title:
			rect = win32gui.GetWindowRect(hwnd)

			result.append({
				"hwnd": hwnd,
				"title": title,
				"left": rect[0],
				"top": rect[1],
				"right": rect[2],
				"bottom": rect[3],
			})

	win32gui.EnumWindows(callback, None)

	return result[0] if result else None
