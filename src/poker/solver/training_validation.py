from poker.solver.training_metrics import SolverTrainingMetrics
from poker.solver.training_objective import SolverTrainingObjective


def evaluate_solver_predictions(
	predicted_probabilities,
	target_probabilities,
	legal_masks,
):
	predictions = tuple(tuple(values) for values in predicted_probabilities)
	targets = tuple(tuple(values) for values in target_probabilities)
	masks = tuple(tuple(values) for values in legal_masks)

	if not predictions:
		raise ValueError("solver validation predictions must not be empty")
	if len(predictions) != len(targets) or len(predictions) != len(masks):
		raise ValueError("solver validation sample counts must match")

	losses = []
	correct = 0

	for predicted, target, legal_mask in zip(predictions, targets, masks):
		if len(predicted) != 6 or len(target) != 6 or len(legal_mask) != 6:
			raise ValueError("solver validation samples must use six actions")

		losses.append(
			SolverTrainingObjective.cross_entropy(
				predicted,
				target,
				legal_mask,
			)
		)

		legal_indices = [
			index
			for index, allowed in enumerate(legal_mask)
			if allowed > 0.0
		]
		if not legal_indices:
			raise ValueError("solver validation sample has no legal actions")

		predicted_action = max(
			legal_indices,
			key=lambda index: (predicted[index], -index),
		)
		target_action = max(
			legal_indices,
			key=lambda index: (target[index], -index),
		)
		if predicted_action == target_action:
			correct += 1

	samples = len(predictions)
	return SolverTrainingMetrics(
		samples=samples,
		mean_loss=sum(losses) / samples,
		accuracy=correct / samples,
	)
