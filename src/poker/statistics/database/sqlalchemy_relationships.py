from dataclasses import dataclass, field


@dataclass
class PlayerWithRelations:
	id: int
	name: str
	profile_id: int | None = None
	statistics_ids: list[int] = field(default_factory=list)


@dataclass
class AgentMemoryLink:
	agent_id: str
	player_id: int
