import time


class PerformanceMeter:
	def __init__(self):
		self.last = time.time()
		self.frames = 0

	def tick(self):
		self.frames += 1

		now = time.time()

		if now - self.last >= 1:
			fps = self.frames
			self.frames = 0
			self.last = now
			return fps

		return None
