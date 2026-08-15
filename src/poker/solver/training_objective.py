from math import log


class SolverTrainingObjective:
	"""Framework-neutral masked soft-policy loss semantics."""

	@staticmethod
	def cross_entropy(predicted_probabilities, target_probabilities, legal_mask):
		if len(predicted_probabilities) != len(target_probabilities):
			raise ValueError("prediction and target sizes must match")
		if len(predicted_probabilities) != len(legal_mask):
			raise ValueError("prediction and mask sizes must match")

		loss = 0.0
		weight = 0.0

		for predicted, target, allowed in zip(
			predicted_probabilities,
			target_probabilities,
			legal_mask,
		):
			if allowed <= 0.0:
				continue
			if predicted <= 0.0:
				raise ValueError("predicted probability must be positive")
			loss -= target * log(predicted)
			weight += target

		if weight == 0.0:
			raise ValueError("target distribution has no legal probability mass")

		return loss / weight
