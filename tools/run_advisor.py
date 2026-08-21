import argparse
import os
import sys
import time

# Подключаем пути
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from poker.agents.neural import NeuralAgent
from poker.learning.observation import LearningObservationEncoder
from poker.vision.state import ScreenState, ScreenPlayer
from poker.vision.translator import ScreenTranslator

def get_dummy_screen_state() -> ScreenState:
    """
    Заглушка модуля компьютерного зрения.
    Здесь должен быть код OpenCV / MSS / Tesseract, делающий скриншот
    и парсящий карты, банк и позиции игроков.
    """
    # Симулируем: Наш ход, мы на префлопе, у нас карманные Тузы.
    return ScreenState(
        is_my_turn=True,
        street_name="preflop",
        board_cards=[],
        hero_hole_cards=["A♠", "A♥"],
        total_pot=1.5, # 1.5 блайнда (SB + BB)
        call_amount_needed=1.0, # Нам нужно докинуть 1 блайнд (если мы рейзим/коллим как CO)
        min_raise_amount=2.0,
        max_raise_amount=100.0,
        players=[
            ScreenPlayer(seat_index=1, name="Hero", is_active=True, is_dealer=True, stack=100.0, current_bet=0.0, cards_dealt=True),
            ScreenPlayer(seat_index=2, name="Opponent", is_active=True, is_dealer=False, stack=98.5, current_bet=1.5, cards_dealt=True),
        ],
        can_fold=True,
        can_check=False,
        can_call=True,
        can_bet=False,
        can_raise=True,
        can_all_in=True
    )

def main():
    parser = argparse.ArgumentParser(description="Запуск Режима Советника (Фаза 8).")
    parser.add_argument("--model", required=True, help="Путь к .pt модели (лучшему агенту)")
    args = parser.parse_args()

    print(f"Инициализация Режима Советника (Advisor Mode)...")
    print(f"Загрузка модели {args.model}...")

    # Для реального стола профили оппонентов из нашей БД не сработают (ведь имена случайные в руме),
    # поэтому мы используем private scope, либо вообще без БД.
    obs_encoder = LearningObservationEncoder(profile_provider=None)

    agent = NeuralAgent(
        model_path=args.model,
        agent_id="ScreenHero",
        observation_encoder=obs_encoder,
        profile_scope="private",
        stochastic=False # В реальной игре мы хотим строго argmax!
    )

    translator = ScreenTranslator(hero_name="Hero")

    print("Советник запущен и следит за экраном. Нажмите Ctrl+C для выхода.")

    try:
        while True:
            # 1. Захват экрана
            screen_state = get_dummy_screen_state()

            # 2. Если не наш ход - ждем
            if not screen_state.is_my_turn:
                time.sleep(1)
                continue

            print("\n[Vision] Обнаружен наш ход! Парсим стол...")

            # 3. Перевод в формат движка
            hand_state = translator.translate_state(screen_state)
            legal_actions = translator.translate_legal_actions(screen_state)

            # 4. Принятие решения нейросетью
            decision = agent.choose_action(hand_state, legal_actions)

            # 5. Вывод рекомендации (Advisor Mode)
            print("==================================================")
            print(f"РАЗДАЧА: Стрит={screen_state.street_name}, Банк={screen_state.total_pot}, Карты={screen_state.hero_hole_cards}")
            print(f"ДОСТУПНЫЕ ДЕЙСТВИЯ: {[act.action_type.name for act in legal_actions.allowed_actions]}")
            print(f"РЕКОМЕНДАЦИЯ НЕЙРОСЕТИ: *** {decision.action.name} {decision.amount if decision.amount > 0 else ''} ***")
            print("==================================================\n")

            print("[System] Ожидание изменения состояния (пауза 5 секунд для тестов).")
            time.sleep(5) # Чтобы заглушка не спамила бесконечно

    except KeyboardInterrupt:
        print("\nБот остановлен пользователем.")

if __name__ == "__main__":
    main()
