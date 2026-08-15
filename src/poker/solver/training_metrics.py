from dataclasses import dataclass


@dataclass(frozen=True)
class SolverTrainingMetrics:
	samples: int
	mean_loss: float
	accuracy: float

	def as_dict(self):
		return {
			"samples": self.samples,
			"mean_loss": self.mean_loss,
			"accuracy": self.accuracy,
		}
