from dataclasses import dataclass


@dataclass
class OpponentMemory:
	agent_id: str
	player_name: str
	hands_observed: int = 0
	vpip: float = 0.0
	pfr: float = 0.0
	aggression: float = 0.0
	confidence: float = 0.0

	def update_confidence(self):
		self.confidence = min(1.0, self.hands_observed / 1000)
