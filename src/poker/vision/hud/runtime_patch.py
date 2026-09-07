\
from __future__ import annotations

from poker.vision.hud.manual_identity import (
	MANUAL_IDENTITIES,
)
from poker.vision.hud.overlay import (
	PokerHudOverlay,
)


_INSTALLED = False


def install_overlay_runtime():
	global _INSTALLED

	if _INSTALLED:
		return

	from poker.vision.debug import (
		table_dashboard,
	)

	from poker.vision.tracking import (
		dynamic_players,
	)

	BaseDashboard = (
		table_dashboard.ScannerDashboard
	)

	BaseTracker = (
		dynamic_players.DynamicPlayerTracker
	)

	class HudScannerDashboard(
		BaseDashboard
	):
		def __init__(
			self,
			*args,
			**kwargs,
		):
			super().__init__(
				*args,
				**kwargs,
			)

			self._poker_hud = (
				PokerHudOverlay()
			)

			self._poker_hud.start()

		def render(
			self,
			table_preview,
			*args,
			**kwargs,
		):
			try:
				self._poker_hud.update(
					table_preview,
					kwargs.get(
						"players",
						[],
					),
					kwargs.get(
						"board_values",
						[],
					),
					kwargs.get(
						"hero_values",
						[],
					),
					kwargs.get(
						"vision_state",
						None,
					),
					kwargs.get(
						"fps",
						0.0,
					),
				)
			except Exception as error:
				self.set_event(
					f"HUD: {error}",
					kind="error",
					duration=5.0,
				)

			return super().render(
				table_preview,
				*args,
				**kwargs,
			)

	class HudDynamicPlayerTracker(
		BaseTracker
	):
		def update_ocr(
			self,
			table_frame,
			panels,
		):
			players = super().update_ocr(
				table_frame,
				panels,
			)

			for player in players:
				seat_index = int(
					getattr(
						player,
						"index",
						-1,
					)
				)

				if seat_index < 0:
					continue

				if bool(
					getattr(
						player,
						"identity_changed",
						False,
					)
				):
					MANUAL_IDENTITIES.clear(
						seat_index,
						reason=(
							"tracker_identity_changed"
						),
					)

				raw_name = str(
					getattr(
						player,
						"raw_name",
						"",
					)
					or ""
				).strip()

				if raw_name == "*****":
					MANUAL_IDENTITIES.clear(
						seat_index,
						reason=(
							"hidden_name_marker"
						),
					)

				manual = (
					MANUAL_IDENTITIES.get(
						seat_index
					)
				)

				if manual is not None:
					player.name = manual.name
					player.confidence = 1.0
					player.identity_pending = False
					setattr(
						player,
						"name_source",
						"manual",
					)
				else:
					setattr(
						player,
						"name_source",
						(
							"unknown"
							if not getattr(
								player,
								"name",
								"",
							)
							else "ocr"
						),
					)

			self.players = players

			return players

	table_dashboard.ScannerDashboard = (
		HudScannerDashboard
	)

	dynamic_players.DynamicPlayerTracker = (
		HudDynamicPlayerTracker
	)

	_INSTALLED = True
