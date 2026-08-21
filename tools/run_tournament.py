import argparse
import os
import shutil
import sys
from collections import defaultdict
from pathlib import Path

# Подключаем пути
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from poker.agents import CallingStationAgent, LAGAgent, ManiacAgent, NitAgent, RandomAgent, TAGAgent
from poker.agents.neural import NeuralAgent
from poker.arena.runner import ArenaRunner
from poker.learning.observation import LearningObservationEncoder
from poker.statistics.database.facade import StatisticsFacade
from poker.statistics.database.postgres_repositories import (
    PostgresMemoryRepository,
    PostgresPlayerRepository,
    PostgresStatisticsRepository,
)
from poker.statistics.database.services import StatisticsService
from poker.statistics.database.sqlalchemy_models import DeclarativeBase
from poker.statistics.opponent_profile import OpponentProfileProvider


def setup_statistics():
    db_url = os.getenv("POKER_DATABASE_URL")
    if not db_url:
        return None, None

    engine = create_engine(db_url, pool_pre_ping=True, pool_recycle=3600)
    DeclarativeBase.metadata.create_all(engine)
    Session = sessionmaker(engine)
    session = Session()

    service = StatisticsService(
        player_repository=PostgresPlayerRepository(session),
        statistics_repository=PostgresStatisticsRepository(session),
        memory_repository=PostgresMemoryRepository(session),
    )
    return session, StatisticsFacade(service)

def main():
    parser = argparse.ArgumentParser(description="Запуск турниров между лучшими моделями (Турнир Чемпионов).")
    parser.add_argument("--tournaments", type=int, default=100, help="Количество турниров для проведения.")
    parser.add_argument("--max-hands", type=int, default=1000, help="Максимальное число раздач на 1 турнир (защита от бесконечных циклов).")
    parser.add_argument("--starting-stack", type=int, default=2000, help="Стартовый стек в фишках.")
    parser.add_argument("--seed", type=int, default=42, help="Базовый сид турниров.")
    args = parser.parse_args()

    session, facade = setup_statistics()
    provider = OpponentProfileProvider(facade) if facade else None
    obs_encoder = LearningObservationEncoder(profile_provider=provider)

    ready_agents_dir = Path("ready_agents")
    models = sorted(ready_agents_dir.glob("*.pt"))

    if not models:
        print(f"В папке {ready_agents_dir} нет сохраненных моделей для турнира!")
        sys.exit(1)

    agents_map = {}

    # Загружаем все нейросети
    print(f"Загружаем {len(models)} моделей на турнир...")
    for model_path in models:
        name = model_path.stem
        agents_map[name] = NeuralAgent(
            model_path=str(model_path),
            agent_id=name,
            observation_encoder=obs_encoder,
            profile_scope="combined"
        )

    # Если ботов меньше 6, добиваем эвристикой
    heuristic_idx = 0
    heuristics = [TAGAgent, LAGAgent, ManiacAgent, NitAgent, CallingStationAgent, RandomAgent]
    while len(agents_map) < 6:
        heuristic_class = heuristics[heuristic_idx % len(heuristics)]
        name = f"{heuristic_class.__name__}_{heuristic_idx}"
        if heuristic_class in [NitAgent, CallingStationAgent]:
            agents_map[name] = heuristic_class()
        else:
            agents_map[name] = heuristic_class(seed=args.seed + heuristic_idx)
        heuristic_idx += 1

    # Если ботов больше 6, берем только топ 6
    if len(agents_map) > 6:
        agents_map = {k: agents_map[k] for k in list(agents_map.keys())[:6]}

    print("\n--- Список участников турнира ---")
    for name in agents_map.keys():
        print(f" - {name}")

    victories = defaultdict(int)

    for t in range(1, args.tournaments + 1):
        # Начинаем турнир
        # Чтобы не писать статистику в БД от турниров (чтобы не портить обучающую базу),
        # мы передаем statistics_service=None.
        runner = ArenaRunner(
            agents=agents_map,
            starting_stack=args.starting_stack,
            statistics_service=None,
            tournament_mode=True
        )

        current_seed = args.seed + t * 1000
        stats = runner.run(hands=args.max_hands, seed=current_seed)

        # Определяем победителя (тот, у кого стек равен starting_stack * 6)
        total_chips_in_play = args.starting_stack * 6
        winner = None
        max_profit = -float('inf')

        for player_name, data in stats.players.items():
            if data.profit > max_profit:
                max_profit = data.profit
                winner = player_name

        if winner:
            victories[winner] += 1
            print(f"Турнир {t}/{args.tournaments} завершен. Победитель: {winner} (Раздач: {stats.hands})")
        else:
            print(f"Турнир {t}/{args.tournaments} завершился в ничью или по лимиту раздач.")

    print("\n=================================")
    print("       ИТОГИ ТУРНИРА             ")
    print("=================================")

    champion = None
    max_wins = -1

    for name, wins in sorted(victories.items(), key=lambda x: x[1], reverse=True):
        winrate = (wins / args.tournaments) * 100
        print(f"{name:<40} | Побед: {wins} ({winrate:.1f}%)")
        if wins > max_wins:
            max_wins = wins
            champion = name

    if session:
        session.close()

    # Сохраняем абсолютного чемпиона в tournament_winner
    if champion:
        champion_path = None
        for p in models:
            if p.stem == champion:
                champion_path = p
                break

        if champion_path:
            out_dir = Path("tournament_winner")
            out_dir.mkdir(exist_ok=True)
            out_file = out_dir / f"CHAMPION_{champion_path.name}"
            shutil.copy(champion_path, out_file)
            print(f"\nАбсолютный чемпион ({champion}) сохранен в папку {out_dir}/!")
        else:
            print(f"\nАбсолютным чемпионом стал скриптовый бот: {champion}. Нейросети нужно учиться дальше!")

if __name__ == "__main__":
    main()
