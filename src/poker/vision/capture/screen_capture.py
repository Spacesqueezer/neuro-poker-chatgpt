import cv2
import mss
import numpy as np


class ScreenCapture:
	def __init__(self, monitor=1):
		self.monitor = monitor
		self.capture = mss.mss()

	def grab(self):
		frame = np.array(self.capture.grab(
			self.capture.monitors[self.monitor]
		))
		return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
