import ctypes
import platform


WDA_EXCLUDEFROMCAPTURE = 0x00000011


def exclude_from_capture(window_name):
	if platform.system() != "Windows":
		return False

	user32 = ctypes.windll.user32

	hwnd = user32.FindWindowW(
		None,
		window_name,
	)

	if not hwnd:
		return False

	return bool(
		user32.SetWindowDisplayAffinity(
			hwnd,
			WDA_EXCLUDEFROMCAPTURE,
		)
	)
