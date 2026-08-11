from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerHandEvent:
	player_name: str
	position: str | None = None
	street_actions: tuple = ()
	entered_pot: bool = False
	raised_preflop: bool = False
	three_bet: bool = False
	showdown: bool = False
	won_showdown: bool = False
