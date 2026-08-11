from dataclasses import dataclass


class Base:
	metadata = None


@dataclass
class ORMEngineConfig:
	url: str
	echo: bool = False
