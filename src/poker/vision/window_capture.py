import mss
import numpy as np
import cv2


class WindowCapture:
	def __init__(self):
		self.sct = mss.mss()

	def grab(self, rect):
		monitor = {
			"left": rect["left"],
			"top": rect["top"],
			"width": rect["right"] - rect["left"],
			"height": rect["bottom"] - rect["top"],
		}

		image = np.array(self.sct.grab(monitor))

		return cv2.cvtColor(
			image,
			cv2.COLOR_BGRA2BGR,
		)
