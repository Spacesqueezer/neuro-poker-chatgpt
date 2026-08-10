from dataclasses import dataclass, field


@dataclass
class ArenaStats:
	hands: int = 0
	seeds: list[int] = field(default_factory=list)
	results: list = field(default_factory=list)
