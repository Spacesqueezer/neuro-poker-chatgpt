import keyboard


class InputHandler:
	def __init__(self):
		self.save_pressed = False
		keyboard.add_hotkey("f8", self._save)

	def _save(self):
		self.save_pressed = True

	def consume_save(self):
		if self.save_pressed:
			self.save_pressed = False
			return True

		return False
