from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerProfile:
	name: str
	style: str
	vpip_target: float
	pfr_target: float
	aggression: float
	bluff_frequency: float
