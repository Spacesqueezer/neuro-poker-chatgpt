import time


class PerformanceMeter:
	def __init__(self):
		self._started_at = time.perf_counter()
		self._frames = 0
		self.fps = 0.0

	def tick(self):
		self._frames += 1
		now = time.perf_counter()
		elapsed = now - self._started_at

		if elapsed >= 0.5:
			self.fps = self._frames / elapsed
			self._frames = 0
			self._started_at = now

		return self.fps
