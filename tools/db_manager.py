import argparse
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from textwrap import dedent

# Подключаем пути
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from poker.statistics.database.sqlalchemy_models import DeclarativeBase, PlayerModel, PlayerStatisticsModel, AgentMemoryModel, PlayerPositionStatisticsModel

def setup_db():
    db_url = os.getenv("POKER_DATABASE_URL")
    if not db_url:
        print("Ошибка: Переменная окружения POKER_DATABASE_URL не установлена!")
        print("Пример: postgresql+psycopg://postgres:password@localhost:5432/neuro_poker")
        sys.exit(1)

    engine = create_engine(db_url)
    DeclarativeBase.metadata.create_all(engine)
    Session = sessionmaker(engine)
    return Session(), engine

def cmd_clear(session, engine):
    print("Удаление всей истории раздач и профилей из базы данных...")
    session.query(AgentMemoryModel).delete()
    session.query(PlayerPositionStatisticsModel).delete()
    session.query(PlayerStatisticsModel).delete()
    session.query(PlayerModel).delete()
    session.commit()
    print("База данных успешно очищена!")

def cmd_init_pool(session):
    print("Генерация пула из 100 ботов...")

    styles = ["tag", "maniac", "nit", "lag", "calling_station", "random"]

    existing_players = session.query(PlayerModel.name).all()
    existing_names = {p[0] for p in existing_players}

    added_count = 0
    # Создаем пропорционально: 30 TAG, 10 Maniac, 20 Nit, 20 LAG, 10 Station, 10 Random
    distribution = {
        "tag": 30,
        "maniac": 10,
        "nit": 20,
        "lag": 20,
        "calling_station": 10,
        "random": 10
    }

    for style, count in distribution.items():
        for i in range(1, count + 1):
            name = f"{style}_{i}"
            if name not in existing_names:
                player = PlayerModel(name=name, profile_id=None)
                session.add(player)
                added_count += 1

    session.commit()
    print(f"Успешно добавлено {added_count} новых ботов в пул!")

def cmd_stats(session):
    print("\n--- Топ-20 активных игроков в БД ---")

    # Берем игроков, сортируем по количеству сыгранных рук
    stats = session.query(PlayerModel, PlayerStatisticsModel)\
        .join(PlayerStatisticsModel, PlayerModel.id == PlayerStatisticsModel.player_id)\
        .order_by(PlayerStatisticsModel.hands.desc())\
        .limit(20).all()

    if not stats:
        print("База данных пуста (нет сыгранных раздач).")
        return

    print(f"{'Имя (Бот)':<20} | {'Hands':<8} | {'VPIP %':<8} | {'PFR %':<8} | {'Aggr':<6} | {'WSD %':<6}")
    print("-" * 65)

    for player, stat in stats:
        vpip = f"{stat.vpip * 100:.1f}" if stat.vpip else "0.0"
        pfr = f"{stat.pfr * 100:.1f}" if stat.pfr else "0.0"
        aggr = f"{stat.aggression:.2f}" if stat.aggression else "0.00"
        wsd = f"{stat.wsd * 100:.1f}" if stat.wsd else "0.0"

        print(f"{player.name:<20} | {stat.hands:<8} | {vpip:<8} | {pfr:<8} | {aggr:<6} | {wsd:<6}")

def main():
    parser = argparse.ArgumentParser(
        description="Менеджер базы данных Neuro Poker.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=dedent('''\
        Примеры использования:
          python tools/db_manager.py init-pool   # Создать 100 профилей ботов
          python tools/db_manager.py clear       # Удалить всех игроков и статистику
          python tools/db_manager.py stats       # Посмотреть статистику игроков
        ''')
    )

    parser.add_argument("command", choices=["init-pool", "clear", "stats"], help="Команда для выполнения")

    args = parser.parse_args()

    session, engine = setup_db()

    try:
        if args.command == "init-pool":
            cmd_init_pool(session)
        elif args.command == "clear":
            cmd_clear(session, engine)
        elif args.command == "stats":
            cmd_stats(session)
    finally:
        session.close()

if __name__ == "__main__":
    main()
