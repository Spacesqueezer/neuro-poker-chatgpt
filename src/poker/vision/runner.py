import time
from concurrent.futures import ThreadPoolExecutor

import cv2

from poker.vision.capture.screen_capture import ScreenCapture
from poker.vision.capture_manager import CaptureManager
from poker.vision.config import load_vision_config
from poker.vision.debug.viewer import (
	WINDOW_NAME,
	close,
	create_window,
	show_frame,
)
from poker.vision.debug.windows_capture import exclude_from_capture
from poker.vision.debug.table_dashboard import ScannerDashboard
from poker.vision.detection.cards import CardDetector
from poker.vision.detection.hero_actions import HeroActionDetector
from poker.vision.detection.multi_anchor import MultiAnchorDetector
from poker.vision.detection.player_panels import PlayerPanelDetector
from poker.vision.performance import PerformanceMeter
from poker.vision.ocr.pot_reader import PotReader
from poker.vision.project_paths import (
	find_project_root,
	get_assets_path,
)
from poker.vision.recognition.card_recognizer import CardRecognizer
from poker.vision.state.screen_state import (
	ScreenState,
	street_from_board,
)
from poker.vision.tracking.hand_state import HandStateTracker
from poker.vision.tracking.dynamic_players import DynamicPlayerTracker
from poker.vision.tracking.fast_hero import FastHeroLocator
from poker.vision.tracking.table_region import (
	build_preview_region,
	estimate_anchor_scale,
)
from poker.vision.tracking.window_geometry import (
	PokerDomWindowWatcher,
)


def _crop(frame, region):
	return frame[
		region.top:region.top + region.height,
		region.left:region.left + region.width,
	]


def _draw_players(preview, players):
	for player in players:
		x1, y1, x2, y2 = player.panel.rect

		color = (
			(0, 255, 0)
			if player.is_hero
			else (255, 0, 255)
		)

		cv2.rectangle(
			preview,
			(x1, y1),
			(x2, y2),
			color,
			2,
		)

		label = (
			f"HERO:{player.name}"
			if player.is_hero
			else (
				player.name
				or f"player_{player.index}"
			)
		)

		if player.action:
			label += f" [{player.action}]"

		cv2.putText(
			preview,
			label,
			(x1, max(18, y1 - 5)),
			cv2.FONT_HERSHEY_SIMPLEX,
			0.45,
			color,
			1,
			cv2.LINE_AA,
		)


def _draw_cards(
	preview,
	cards,
	values,
	color,
	prefix,
):
	for index, card in enumerate(cards):
		x1, y1, x2, y2 = card.rect

		cv2.rectangle(
			preview,
			(x1, y1),
			(x2, y2),
			color,
			2,
		)

		value = (
			values[index]
			if index < len(values)
			else "?"
		)

		cv2.putText(
			preview,
			f"{prefix}:{value}",
			(x1, max(18, y1 - 5)),
			cv2.FONT_HERSHEY_SIMPLEX,
			0.48,
			color,
			1,
			cv2.LINE_AA,
		)


def _panel_only_players(panels):
	return [
		type(
			"PanelOnlyPlayer",
			(),
			{
				"index": index,
				"panel": panel,
				"name": "",
				"action": None,
				"is_hero": False,
			},
		)()
		for index, panel in enumerate(panels)
	]


def _find_hero_panel(players):
	for player in players:
		if player.is_hero:
			return player.panel

	return None


def _decorate_fast_hero(
	players,
	panels,
	hero_panel,
	hero_name,
):
	if hero_panel is None:
		return players

	rows = list(
		players
		if len(players) == len(panels)
		else _panel_only_players(
			panels
		)
	)

	best_index = None
	best_distance = None

	for index, player in enumerate(
		rows
	):
		distance = (
			(
				player.panel.center[0]
				- hero_panel.center[0]
			) ** 2
			+ (
				player.panel.center[1]
				- hero_panel.center[1]
			) ** 2
		) ** 0.5

		if (
			best_distance is None
			or distance < best_distance
		):
			best_distance = distance
			best_index = index

	if best_index is None:
		return rows

	player = rows[
		best_index
	]

	if not getattr(
		player,
		"is_hero",
		False,
	):
		# Не мутируем объект DynamicPlayerTracker: его identity state
		# остаётся консервативным для статистики. Это только runtime view.
		player = type(
			"RuntimeHeroPlayer",
			(),
			{
				"index": getattr(
					player,
					"index",
					best_index,
				),
				"panel": player.panel,
				"name": hero_name,
				"action": getattr(
					player,
					"action",
					None,
				),
				"is_hero": True,
				"identity_pending": getattr(
					player,
					"identity_pending",
					False,
				),
			},
		)()

		rows[
			best_index
		] = player

	return rows


def _scan_cards(
	card_detector,
	table_frame,
	hero_panel,
):
	return (
		card_detector.detect_board(
			table_frame
		),
		card_detector.detect_hero(
			table_frame,
			hero_panel,
		),
	)


def _recognize_cards(
	card_recognizer,
	table_frame,
	board_cards,
	hero_cards,
	board_signature,
	hero_signature,
):
	board_values = []

	hero_values = []

	if board_cards:
		board_values = (
			card_recognizer.recognize_many(
				table_frame,
				board_cards,
			)
		)

	if hero_cards:
		hero_values = (
			card_recognizer.recognize_many(
				table_frame,
				hero_cards,
			)
		)

	return (
		board_signature,
		hero_signature,
		board_values,
		hero_values,
	)


def run():
	config = load_vision_config()

	project_root = find_project_root()
	assets_path = get_assets_path()

	# Runtime information is shown in the scanner dashboard instead of
	# continuously spamming the console.

	capture = ScreenCapture(
		config["capture"]["monitor"]
	)

	anchor_detector = MultiAnchorDetector(
		assets_path / "anchor",
		config["anchor"]["threshold"],
	)

	panel_detector = PlayerPanelDetector()
	card_detector = CardDetector()
	card_recognizer = CardRecognizer()
	hand_state = HandStateTracker()
	action_detector = HeroActionDetector()
	pot_reader = PotReader()

	player_tracker = DynamicPlayerTracker(
		config["hero_name"],
	)

	fast_hero = FastHeroLocator(
		project_root,
		config["hero_name"],
	)

	capture_manager = CaptureManager(
		config.get(
			"captures_folder",
			"captures",
		)
	)

	performance = PerformanceMeter()
	executor = ThreadPoolExecutor(
		max_workers=4
	)

	create_window()

	exclude_from_capture(
		WINDOW_NAME
	)

	dashboard = ScannerDashboard()
	dashboard.set_event(
		f"Hero: {config['hero_name']}",
		kind="info",
		duration=5.0,
	)

	table_region = None
	table_anchor_scale = 1.0
	window_watcher = PokerDomWindowWatcher()
	last_window_poll = 0.0
	resize_relock_requested = False

	panels = []
	players = []

	board_cards = []
	board_values = []
	hero_cards = []
	hero_values = []

	board_signature = None
	hero_signature = None

	panel_future = None
	ocr_future = None
	card_future = None
	card_ocr_future = None

	last_panel_start = 0.0
	last_player_count = None
	last_name_log = None
	last_card_scan = 0.0
	last_card_ocr = 0.0
	last_card_log = None
	last_fast_state_scan = 0.0
	last_pot_scan = 0.0
	last_state_log = None
	vision_state = None
	action_state = action_detector.detect(
		cv2.imread(str(project_root / "assets" / "__missing__.png"))
	) if False else None
	total_pot = None

	while True:
		loop_started = time.perf_counter()
		frame = capture.grab()

		if table_region is None:
			anchors = anchor_detector.find(
				frame,
				scale_hint=table_anchor_scale,
				wide_search=True,
			)

			table_region = build_preview_region(
				frame,
				anchors,
			)

			if table_region is None:
				fps = performance.tick()

				preview = dashboard.render_searching(
					frame,
					fps,
					screen_size=(
						frame.shape[1],
						frame.shape[0],
					),
				)

				key = show_frame(
					preview,
					1.0,
				)

				if key == ord("q"):
					break

				continue

			table_anchor_scale = (
				estimate_anchor_scale(
					anchors
				)
			)

			window_watcher.poll()
			last_window_poll = time.monotonic()

			dashboard.set_event(
				"Table locked",
				kind="ok",
			)

		now = time.monotonic()

		# НЕ гоняем matchTemplate по всему монитору каждые 0.9 секунды.
		# Это и было причиной падения до ~0.2 FPS.
		#
		# Вместо этого раз в 0.5 секунды спрашиваем Windows API:
		# изменились ли координаты/размер client area PokerDom.
		# Такой poll практически бесплатный.
		if now - last_window_poll >= 0.5:
			window_changed, _ = (
				window_watcher.poll()
			)

			last_window_poll = now

			if window_changed:
				resize_relock_requested = True

		# Тяжёлый multi-scale anchor search выполняется ТОЛЬКО после
		# реального move/resize окна, а не постоянно.
		if resize_relock_requested:
			anchors = anchor_detector.find(
				frame,
				scale_hint=table_anchor_scale,
				wide_search=True,
			)

			new_region = build_preview_region(
				frame,
				anchors,
			)

			if new_region is not None:
				table_region = new_region
				table_anchor_scale = (
					estimate_anchor_scale(
						anchors
					)
				)

				panels = []
				players = []
				fast_hero.reset()

				board_cards = []
				board_values = []
				hero_cards = []
				hero_values = []

				board_signature = None
				hero_signature = None

				hand_state.reset_geometry_only()

				last_player_count = None
				last_name_log = None
				last_card_log = None
				last_state_log = None

				vision_state = None
				total_pot = None
				action_state = None

				resize_relock_requested = False

				dashboard.set_event(
					"Table resized / moved — auto re-lock",
					kind="warning",
					duration=4.0,
				)

		table_frame = _crop(
			frame,
			table_region,
		)

		if (
			panel_future is None
			and now - last_panel_start >= 1.6
		):
			panel_future = executor.submit(
				panel_detector.detect,
				table_frame.copy(),
			)
			last_panel_start = now

		if (
			panel_future is not None
			and panel_future.done()
		):
			try:
				new_panels = panel_future.result()

				if new_panels:
					panels = new_panels
			except Exception as error:
				dashboard.set_event(
					f"Panel detector: {error}",
					kind="error",
					duration=8.0,
				)

			panel_future = None

			if (
				panels
				and len(panels)
				!= last_player_count
			):
				last_player_count = len(
					panels
				)

				dashboard.set_event(
					f"Players detected: {last_player_count}",
					kind="info",
				)

		if (
			panels
			and ocr_future is None
			and now
			- player_tracker.last_scan
			>= 0.8
		):
			ocr_future = executor.submit(
				player_tracker.update_ocr,
				table_frame.copy(),
				list(panels),
			)

		if (
			ocr_future is not None
			and ocr_future.done()
		):
			try:
				players = ocr_future.result()

				confirmed_hero = _find_hero_panel(
					players
				)

				if confirmed_hero is not None:
					fast_hero.remember(
						confirmed_hero,
						table_frame.shape,
					)

				name_log = tuple(
					(
						player.name,
						player.action,
						player.is_hero,
					)
					for player in players
				)

				if name_log != last_name_log:
					last_name_log = name_log
			except Exception as error:
				dashboard.set_event(
					f"Name worker: {error}",
					kind="error",
					duration=8.0,
				)

			ocr_future = None

		# HERO ищем быстрым template/cached locator сразу по panels.
		# Не ждём, пока полный Tesseract OCR всех игроков закончит цикл.
		hero_panel = fast_hero.locate(
			table_frame,
			panels,
		)

		if hero_panel is None:
			hero_panel = _find_hero_panel(
				players
			)

			if hero_panel is not None:
				fast_hero.remember(
					hero_panel,
					table_frame.shape,
				)

		draw_players = _decorate_fast_hero(
			players,
			panels,
			hero_panel,
			config["hero_name"],
		)

		# Геометрию карт тоже уводим из main loop.
		# Раньше detect_board + detect_hero выполнялись синхронно каждые
		# 0.10 сек и сами по себе давали заметный jitter FPS.
		if (
			card_future is None
			and now - last_card_scan >= 0.18
		):
			card_future = executor.submit(
				_scan_cards,
				card_detector,
				table_frame.copy(),
				hero_panel,
			)

			last_card_scan = now

		if (
			card_future is not None
			and card_future.done()
		):
			try:
				(
					new_board_cards,
					new_hero_cards,
				) = card_future.result()

				new_board_signature = (
					card_detector.signature(
						new_board_cards
					)
				)

				new_hero_signature = (
					card_detector.signature(
						new_hero_cards
					)
				)

				hand_state.observe_geometry(
					board_count=len(
						new_board_cards
					),
					hero_count=len(
						new_hero_cards
					),
				)

				if (
					new_board_signature
					!= board_signature
				):
					board_cards = new_board_cards
					board_signature = (
						new_board_signature
					)

				if (
					new_hero_signature
					!= hero_signature
				):
					hero_cards = new_hero_cards
					hero_signature = (
						new_hero_signature
					)
			except Exception as error:
				dashboard.set_event(
					f"Card detector: {error}",
					kind="error",
					duration=6.0,
				)

			card_future = None

		# Даже template recognition иногда проваливается в Tesseract fallback.
		# Поэтому распознавание карт тоже не должно блокировать GUI/main loop.
		if (
			card_ocr_future is None
			and now - last_card_ocr >= 0.75
			and (
				board_cards
				or hero_cards
			)
		):
			card_ocr_future = executor.submit(
				_recognize_cards,
				card_recognizer,
				table_frame.copy(),
				list(board_cards),
				list(hero_cards),
				board_signature,
				hero_signature,
			)

			last_card_ocr = now

		if (
			card_ocr_future is not None
			and card_ocr_future.done()
		):
			try:
				(
					result_board_signature,
					result_hero_signature,
					raw_board,
					raw_hero,
				) = card_ocr_future.result()

				# Не применяем результат старой геометрии, если cards уже
				# успели измениться.
				if (
					result_board_signature
					== board_signature
				):
					if board_cards:
						board_values = (
							hand_state.update_board(
								raw_board
							)
						)
					else:
						board_values = (
							hand_state.board_values
						)

				if (
					result_hero_signature
					== hero_signature
				):
					if hero_cards:
						hero_values = (
							hand_state.update_hero(
								raw_hero
							)
						)
					else:
						hero_values = (
							hand_state.hero_values
						)

				board_values = (
					hand_state.board_values
				)

				hero_values = (
					hand_state.hero_values
				)

				card_log = (
					tuple(board_values),
					tuple(hero_values),
				)

				if card_log != last_card_log:
					last_card_log = card_log
			except Exception as error:
				dashboard.set_event(
					f"Card OCR: {error}",
					kind="error",
					duration=6.0,
				)

			card_ocr_future = None

		if now - last_fast_state_scan >= 0.10:
			action_state = action_detector.detect(
				table_frame
			)
			last_fast_state_scan = now

		if now - last_pot_scan >= 0.75:
			new_pot = pot_reader.read(
				table_frame
			)

			if new_pot is not None:
				total_pot = new_pot

			last_pot_scan = now

		if action_state is not None:
			vision_state = ScreenState(
				is_my_turn=action_state.is_my_turn,
				street_name=hand_state.street_name,
				board_cards=list(board_values),
				hero_hole_cards=list(hero_values),
				total_pot=total_pot,
				can_fold=action_state.can_fold,
				can_check=action_state.can_check,
				can_call=action_state.can_call,
				can_bet=action_state.can_bet,
				can_raise=action_state.can_raise,
				can_all_in=action_state.can_all_in,
			)

			state_log = tuple(
				vision_state.to_dict().items()
			)

			if state_log != last_state_log:
				last_state_log = state_log

		preview = table_frame.copy()

		_draw_players(
			preview,
			draw_players,
		)

		_draw_cards(
			preview,
			board_cards,
			board_values,
			(0, 255, 255),
			"B",
		)

		_draw_cards(
			preview,
			hero_cards,
			hero_values,
			(0, 255, 0),
			"H",
		)

		if action_state is not None:
			for button in action_state.buttons:
				x1, y1, x2, y2 = button.rect

				cv2.rectangle(
					preview,
					(x1, y1),
					(x2, y2),
					(255, 255, 255),
					2,
				)

				cv2.putText(
					preview,
					button.action,
					(x1, max(18, y1 - 5)),
					cv2.FONT_HERSHEY_SIMPLEX,
					0.52,
					(255, 255, 255),
					1,
					cv2.LINE_AA,
				)

		fps = performance.tick()

		preview = dashboard.render(
			preview,
			screen_size=(
				frame.shape[1],
				frame.shape[0],
			),
			locked=True,
			fps=fps,
			panels=panels,
			players=draw_players,
			board_values=board_values,
			hero_values=hero_values,
			vision_state=vision_state,
			action_state=action_state,
			panel_worker_busy=(
				panel_future is not None
			),
			ocr_worker_busy=(
				ocr_future is not None
			),
			card_worker_busy=(
				card_future is not None
				or card_ocr_future is not None
			),
			hero_locked=(
				hero_panel is not None
			),
			board_box_count=len(
				board_cards
			),
			hero_box_count=len(
				hero_cards
			),
		)

		key = show_frame(
			preview,
			1.0,
		)

		if key == ord("q"):
			break

		if key == ord("r"):
			table_region = None
			table_anchor_scale = 1.0
			window_watcher.reset()
			last_window_poll = 0.0
			resize_relock_requested = False

			panels = []
			players = []
			board_cards = []
			board_values = []
			hero_cards = []
			hero_values = []
			board_signature = None
			hero_signature = None
			hand_state.reset_all()
			last_player_count = None
			last_name_log = None
			last_card_log = None
			last_state_log = None
			vision_state = None
			total_pot = None
			action_state = None

			dashboard.set_event(
				"Manual table re-lock",
				kind="warning",
			)
			continue

		if key in {
			ord("s"),
			ord("S"),
			ord("ы"),
			ord("Ы"),
			251,
			219,
		}:
			output = capture_manager.save_dynamic(
				table_frame,
				draw_players,
				board_cards=board_cards,
				hero_cards=hero_cards,
			)

			dashboard.set_event(
				f"Capture saved: {output.name}",
				kind="ok",
				duration=5.0,
			)

		target_fps = max(
			1,
			config["capture"].get(
				"fps_limit",
				30,
			),
		)

		elapsed = (
			time.perf_counter()
			- loop_started
		)

		sleep_time = (
			1.0 / target_fps
			- elapsed
		)

		if sleep_time > 0:
			time.sleep(
				sleep_time
			)

	executor.shutdown(
		wait=False,
		cancel_futures=True,
	)

	close()


if __name__ == "__main__":
	run()
