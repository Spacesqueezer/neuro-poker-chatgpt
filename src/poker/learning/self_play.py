import random
from pathlib import Path

class ModelPool:
	def __init__(self, directory):
		self.directory = Path(directory)
		self.directory.mkdir(parents=True, exist_ok=True)

	def list_models(self):
		return sorted(self.directory.glob("*.pt"))

	def sample_model(self, seed=None):
		models = self.list_models()
		if not models:
			return None

		# Sample with a simple random choice. Can be extended to prioritize recent models.
		rng = random.Random(seed)
		return rng.choice(models)

	def add_model(self, model_path):
		model_path = Path(model_path)
		if not model_path.exists():
			raise FileNotFoundError(f"Model file {model_path} does not exist.")

		dest = self.directory / model_path.name
		# If the source is different from destination, copy it
		if model_path.resolve() != dest.resolve():
			dest.write_bytes(model_path.read_bytes())

		return dest
