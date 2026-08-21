import argparse
import os
import sys
import random
from pathlib import Path

# Подключаем пути
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from poker.agents.neural import NeuralAgent
from poker.agents import RandomAgent, CallingStationAgent, NitAgent, ManiacAgent, TAGAgent, LAGAgent
from poker.arena.session import ArenaSession
from poker.api import ActionDecision, play_hand
from poker.game.actions import PlayerAction
from poker.learning.observation import LearningObservationEncoder
from poker.statistics.opponent_profile import OpponentProfileProvider
from poker.game.round_manager import GameStreet

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from poker.statistics.database.sqlalchemy_models import DeclarativeBase
from poker.statistics.database.postgres_repositories import (
    PostgresPlayerRepository,
    PostgresStatisticsRepository,
    PostgresMemoryRepository,
)
from poker.statistics.database.services import StatisticsService
from poker.statistics.database.facade import StatisticsFacade

ACTION_COMMANDS = {
	"fold": PlayerAction.FOLD,
	"check": PlayerAction.CHECK,
	"call": PlayerAction.CALL,
	"bet": PlayerAction.BET,
	"raise": PlayerAction.RAISE,
	"all-in": PlayerAction.ALL_IN,
	"allin": PlayerAction.ALL_IN,
}

AMOUNT_COMMANDS = {"bet", "raise"}

class HumanAgent:
    def __init__(self, name="Human"):
        self.name = name

    def choose_action(self, state, legal_actions):
        print(f"\n--- Твой ход, {self.name}! ---")
        print(f"Доступные действия: {[a.value for a in legal_actions.actions]}")

        while True:
            try:
                command = input("Действие (например: call, fold, raise 50) > ").strip().lower()
                parts = command.split()
                if not parts:
                    continue

                name = parts[0]
                if name not in ACTION_COMMANDS:
                    print("Неизвестная команда. Доступны: check, call, fold, bet N, raise N, all-in")
                    continue

                action = ACTION_COMMANDS[name]
                amount = 0

                if name in AMOUNT_COMMANDS:
                    if len(parts) != 2:
                        print(f"Использование: {name} СУММА")
                        continue
                    try:
                        amount = int(parts[1])
                    except ValueError:
                        print("Сумма должна быть числом!")
                        continue

                if not legal_actions.allows(action, amount):
                    print(f"Нелегальное действие! (Min bet/raise: {legal_actions.min_bet}/{legal_actions.min_raise_to}, Max: {legal_actions.max_bet}/{legal_actions.max_raise_to}, Call amount: {legal_actions.call_amount})")
                    continue

                return ActionDecision(action, amount)

            except (EOFError, KeyboardInterrupt):
                print("\nВыход из игры...")
                sys.exit(0)

def setup_statistics():
    db_url = os.getenv("POKER_DATABASE_URL")
    if not db_url:
        return None, None

    engine = create_engine(db_url)
    DeclarativeBase.metadata.create_all(engine)
    Session = sessionmaker(engine)
    session = Session()

    service = StatisticsService(
        player_repository=PostgresPlayerRepository(session),
        statistics_repository=PostgresStatisticsRepository(session),
        memory_repository=PostgresMemoryRepository(session),
    )
    return session, StatisticsFacade(service)

def format_cards(cards):
	return " ".join(str(card) for card in cards) or "-"

def print_game_state(history):
    # This acts as a hand_observer to print what happened
    pass # We will use a custom decision observer to print the state instead

def print_state_for_human(state, legal_actions):
    print("\n" + "="*50)
    print(f"Улица: {state.street.upper()}")
    print(f"Борд:  {format_cards(state.board)}")
    print(f"Банк:  {state.pot} (Текущая ставка: {state.target_bet})")
    print(f"Твои карты: {format_cards(state.hole_cards)}")
    print("-" * 50)
    for p in state.players:
        status = "folded" if p.folded else "active"
        print(f"[{p.position}] {p.name}: Фишки={p.chips}, В банке={p.total_contribution} ({status})")
    print("="*50)

def main():
    parser = argparse.ArgumentParser(description="Интерактивная игра против нейросети.")
    parser.add_argument("--model", required=True, help="Путь к .pt модели (например, ready_agents/best_model.pt)")
    parser.add_argument("--opponents", nargs="*", choices=["tag", "maniac", "nit", "calling_station", "lag", "random"], default=[], help="Дополнительные скриптовые боты за столом")
    parser.add_argument("--starting-stack", type=int, default=200, help="Стартовый стек")
    args = parser.parse_args()

    session, facade = setup_statistics()
    provider = OpponentProfileProvider(facade) if facade else None
    obs_encoder = LearningObservationEncoder(profile_provider=provider)

    agents = {}

    # 1. Человек
    agents["Human"] = HumanAgent("Human")

    # 2. Нейросеть
    print(f"Загрузка модели {args.model}...")
    agents["NeuralBot"] = NeuralAgent(
        model_path=args.model,
        agent_id="NeuralBot",
        observation_encoder=obs_encoder,
        profile_scope="combined",
        stochastic=True # Делаем её чуть более непредсказуемой (как в self-play)
    )

    # 3. Эвристика
    for i, opp in enumerate(args.opponents):
        name = f"{opp}_{i}"
        if opp == "tag":
            agents[name] = TAGAgent()
        elif opp == "maniac":
            agents[name] = ManiacAgent()
        elif opp == "nit":
            agents[name] = NitAgent()
        elif opp == "calling_station":
            agents[name] = CallingStationAgent()
        elif opp == "lag":
            agents[name] = LAGAgent()
        elif opp == "random":
            agents[name] = RandomAgent()

    print(f"\nСтол сформирован. Игроков: {len(agents)}")
    print("Твои оппоненты:", ", ".join([k for k in agents.keys() if k != "Human"]))

    # Чтобы движок мог передавать state в decision_observer, мы создадим враппер
    from poker.api.hand_state import build_hand_state_view

    def interactive_decision_observer(hand_state, legal_actions, decision):
        # Если сейчас ходит человек, печатаем состояние стола до его хода
        if hand_state.acting_player == "Human":
            print_state_for_human(hand_state, legal_actions)

        # Печатаем действие ВСЕХ игроков
        print(f">>> {hand_state.acting_player} совершает действие: {decision.action.value} {decision.amount if decision.amount > 0 else ''}")

    arena_session = ArenaSession.create(players=agents.keys(), starting_stack=args.starting_stack, tournament_mode=False)

    hand_number = 1
    players_list = list(agents.keys())

    while True:
        if arena_session.is_finished():
            print("\nУ кого-то закончились фишки! Игра окончена.")
            break

        print(f"\n\n{'*'*20} РАЗДАЧА {hand_number} {'*'*20}")
        dealer_name = players_list[(hand_number - 1) % len(players_list)]

        try:
            result = arena_session.play_next_hand(
                agents,
                seed=random.randint(0, 1000000),
                dealer_name=dealer_name,
                decision_observer=interactive_decision_observer
            )

            # Показываем результаты раздачи
            print("\n--- Итоги раздачи ---")
            for player, stack in result.final_stacks.items():
                diff = stack - arena_session.stacks[player] # Note: session stacks are updated inside play_next_hand
                diff_str = f"+{diff}" if diff > 0 else str(diff)
                print(f"{player}: {stack} ({diff_str})")

            hand_number += 1
            input("\nНажми Enter для следующей раздачи...")

        except (EOFError, KeyboardInterrupt):
            print("\nИгра прервана пользователем.")
            break

    if session:
        session.close()

if __name__ == "__main__":
    main()
