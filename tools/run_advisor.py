import argparse
import os
import sys
import time

# Подключаем пути
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from poker.agents.neural import NeuralAgent
from poker.learning.observation import LearningObservationEncoder
from poker.vision.state import ScreenPlayer, ScreenState
from poker.vision.translator import ScreenTranslator
from poker.vision.state_extractor import GameStateExtractor

def _get_dummy_screen_state_from_extractor(extracted_state) -> ScreenState:
    """
    Translates the state extracted from OpenCV/Tesseract into the ScreenState format
    expected by the ScreenTranslator.
    """

    # In a real implementation we would dynamically detect this.
    # For now, we simulate being in preflop based on empty board cards.
    hero_dict = extracted_state.get('hero', {})

    # Convert opponents dictionary to ScreenPlayer objects
    players = []

    # Hero player
    players.append(
        ScreenPlayer(
            seat_index=1,
            name=hero_dict.get('name', 'Hero'),
            is_active=True,
            is_dealer=True,
            stack=hero_dict.get('stack', 0.0) or 0.0,
            current_bet=0.0,
            cards_dealt=True
        )
    )

    # Opponents
    seat_idx = 2
    for opp_name, info in extracted_state.get('opponents', {}).items():
        players.append(
            ScreenPlayer(
                seat_index=seat_idx,
                name=opp_name,
                is_active=True,
                is_dealer=False,
                stack=info.get('stack', 0.0) or 0.0,
                current_bet=0.0,
                cards_dealt=True
            )
        )
        seat_idx += 1

    return ScreenState(
        is_my_turn=True, # Assuming it's our turn when extracting
        street_name="preflop" if not extracted_state.get('board') else "flop",
        board_cards=extracted_state.get('board', []),
        hero_hole_cards=["A♠", "A♥"], # Hardcoded for now until we parse cards
        total_pot=extracted_state.get('pot', 0.0) or 0.0,
        call_amount_needed=0.0,
        min_raise_amount=2.0,
        max_raise_amount=100.0,
        players=players,
        can_fold=True,
        can_check=True,
        can_call=True,
        can_bet=True,
        can_raise=True,
        can_all_in=True
    )

def main():
    parser = argparse.ArgumentParser(description="Запуск Режима Советника (Фаза 8).")
    parser.add_argument("--model", required=False, help="Путь к .pt модели (лучшему агенту)")
    parser.add_argument("--image", required=False, help="Тестовое изображение для парсинга")
    args = parser.parse_args()

    print("Инициализация Режима Советника (Advisor Mode)...")

    if args.model:
        print(f"Загрузка модели {args.model}...")
        obs_encoder = LearningObservationEncoder(profile_provider=None)
        agent = NeuralAgent(
            model_path=args.model,
            agent_id="ScreenHero",
            observation_encoder=obs_encoder,
            profile_scope="private",
            stochastic=False
        )
    else:
        print("Внимание: Запуск без нейросети (только парсинг экрана).")
        agent = None

    translator = ScreenTranslator(hero_name="Hero")
    extractor = GameStateExtractor()

    print("Советник запущен и следит за экраном. Нажмите Ctrl+C для выхода.")

    try:
        while True:
            # 1. Захват экрана
            if args.image:
                try:
                    raw_state = extractor.extract_state(args.image)
                    screen_state = _get_dummy_screen_state_from_extractor(raw_state)
                except Exception as e:
                    print(f"Ошибка парсинга: {e}")
                    time.sleep(2)
                    continue
            else:
                # Fallback to screenshot if mss is installed
                try:
                    from mss import mss
                    with mss() as sct:
                        # Use cross-platform temporary directory
                        import tempfile
                        tmp_dir = tempfile.gettempdir()
                        screenshot_path = os.path.join(tmp_dir, "advisor_capture.png")
                        sct.shot(mon=1, output=screenshot_path)
                        raw_state = extractor.extract_state(screenshot_path)
                        screen_state = _get_dummy_screen_state_from_extractor(raw_state)
                except ImportError:
                    print("Модуль mss не установлен! Используйте --image <путь_к_изображению>")
                    break

            # 2. Если не наш ход - ждем
            if not screen_state.is_my_turn:
                time.sleep(1)
                continue

            print("\n[Vision] Обнаружен наш ход! Парсим стол...")

            # 3. Перевод в формат движка
            hand_state = translator.translate_state(screen_state)
            legal_actions = translator.translate_legal_actions(screen_state)

            # 4. Принятие решения нейросетью
            print("==================================================")
            print(f"РАЗДАЧА: Стрит={screen_state.street_name}, Банк={screen_state.total_pot}, Карты={screen_state.hero_hole_cards}")

            # Print parsed opponents
            print("ОППОНЕНТЫ:")
            for p in screen_state.players:
                if p.seat_index != 1:
                    print(f" - {p.name} (Seat {p.seat_index}): Stack {p.stack}")

            print(f"ДОСТУПНЫЕ ДЕЙСТВИЯ: {[act.name for act in legal_actions.actions]}")

            if agent:
                decision = agent.choose_action(hand_state, legal_actions)
                print(f"РЕКОМЕНДАЦИЯ НЕЙРОСЕТИ: *** {decision.action.name} {decision.amount if decision.amount > 0 else ''} ***")
            else:
                print("РЕКОМЕНДАЦИЯ НЕЙРОСЕТИ: *** ОТСУТСТВУЕТ (Модель не загружена) ***")

            print("==================================================\n")

            if args.image:
                print("[System] Режим одного изображения. Выход.")
                break

            print("[System] Ожидание изменения состояния (пауза 5 секунд для тестов).")
            time.sleep(5)

    except KeyboardInterrupt:
        print("\nБот остановлен пользователем.")

if __name__ == "__main__":
    main()
