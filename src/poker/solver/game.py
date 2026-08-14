from dataclasses import dataclass
from typing import Hashable, Protocol


@dataclass(frozen=True)
class InitialNode:
	state: object
	probability: float


class TwoPlayerSolverGame(Protocol):
	def initial_nodes(self) -> tuple[InitialNode, ...]: ...

	def player_to_act(self, state: object) -> int: ...

	def is_terminal_node(self, state: object) -> bool: ...

	def terminal_node_utility(self, state: object, player: int) -> float: ...

	def information_set_for_node(
		self,
		state: object,
		player: int,
	) -> Hashable: ...

	def legal_actions(self, state: object) -> tuple[str, ...]: ...

	def next_node(self, state: object, action: str) -> object: ...
