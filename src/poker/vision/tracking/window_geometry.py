import ctypes
import ctypes.wintypes
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class WindowRect:
	left: int
	top: int
	right: int
	bottom: int

	@property
	def width(self):
		return max(
			0,
			self.right - self.left,
		)

	@property
	def height(self):
		return max(
			0,
			self.bottom - self.top,
		)


class PokerDomWindowWatcher:
	"""
	Очень дешёвый watcher геометрии окна PokerDom.

	Никакого cv2.matchTemplate здесь нет.
	Windows API просто сообщает координаты client area окна.
	"""

	def __init__(
		self,
		title_token="pokerdom",
	):
		self.title_token = (
			title_token
			.lower()
		)

		self.last_rect = None

	def poll(self):
		rect = self._find_client_rect()

		if rect is None:
			return (
				False,
				None,
			)

		if self.last_rect is None:
			self.last_rect = rect

			return (
				False,
				rect,
			)

		changed = self._meaningfully_changed(
			self.last_rect,
			rect,
		)

		self.last_rect = rect

		return (
			changed,
			rect,
		)

	def reset(self):
		self.last_rect = None

	def _find_client_rect(self):
		if os.name != "nt":
			return None

		user32 = ctypes.windll.user32

		found = []

		WNDENUMPROC = ctypes.WINFUNCTYPE(
			ctypes.c_bool,
			ctypes.c_void_p,
			ctypes.c_void_p,
		)

		def callback(
			hwnd,
			lparam,
		):
			if not user32.IsWindowVisible(
				hwnd
			):
				return True

			length = user32.GetWindowTextLengthW(
				hwnd
			)

			if length <= 0:
				return True

			buffer = ctypes.create_unicode_buffer(
				length + 1
			)

			user32.GetWindowTextW(
				hwnd,
				buffer,
				length + 1,
			)

			title = (
				buffer.value
				.lower()
			)

			if self.title_token not in title:
				return True

			rect = ctypes.wintypes.RECT()

			if not user32.GetClientRect(
				hwnd,
				ctypes.byref(
					rect
				),
			):
				return True

			point = ctypes.wintypes.POINT(
				0,
				0,
			)

			if not user32.ClientToScreen(
				hwnd,
				ctypes.byref(
					point
				),
			):
				return True

			width = (
				rect.right
				- rect.left
			)

			height = (
				rect.bottom
				- rect.top
			)

			if (
				width < 300
				or height < 250
			):
				return True

			found.append(
				WindowRect(
					left=int(
						point.x
					),
					top=int(
						point.y
					),
					right=int(
						point.x
						+ width
					),
					bottom=int(
						point.y
						+ height
					),
				)
			)

			return True

		user32.EnumWindows(
			WNDENUMPROC(
				callback
			),
			0,
		)

		if not found:
			return None

		# Если вдруг открыто несколько PokerDom окон, берём самое большое.
		return max(
			found,
			key=lambda item: (
				item.width
				* item.height
			),
		)

	def _meaningfully_changed(
		self,
		old,
		new,
	):
		return (
			abs(
				new.left
				- old.left
			) >= 6
			or abs(
				new.top
				- old.top
			) >= 6
			or abs(
				new.width
				- old.width
			) >= 8
			or abs(
				new.height
				- old.height
			) >= 8
		)
