import argparse
import json
import os
import sys
from pathlib import Path

# Подключаем пути
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

def analyze_datasets(datasets_dir):
    report = ["### Анализ датасетов (Self-Play) ###"]
    dir_path = Path(datasets_dir)
    if not dir_path.exists():
        report.append("Папка с датасетами не найдена.")
        return report

    files = sorted(dir_path.glob("*.jsonl"))
    if not files:
        report.append("Датасеты .jsonl не найдены.")
        return report

    for file in files:
        lines = 0
        rewards = []
        with open(file, encoding="utf-8") as f:
            for line in f:
                lines += 1
                try:
                    data = json.loads(line)
                    if "reward" in data:
                        rewards.append(data["reward"])
                except:
                    pass

        unique_rewards = len(set(rewards))
        avg_reward = sum(rewards) / len(rewards) if rewards else 0

        report.append(f"Файл: {file.name}")
        report.append(f" - Строк (семплов): {lines}")
        report.append(f" - Уникальных значений reward: {unique_rewards} (если 1-2, то игры слишком однообразны)")
        report.append(f" - Средний reward: {avg_reward:.2f}")

    report.append("")
    return report

def analyze_benchmarks(artifacts_dir):
    report = ["### Анализ Бенчмарков ###"]
    dir_path = Path(artifacts_dir)
    if not dir_path.exists():
        report.append("Папка с артефактами не найдена.")
        return report

    files = sorted(dir_path.glob("benchmark_iter_*.json"))
    if not files:
        report.append("Файлы бенчмарков не найдены.")
        return report

    all_bb_100 = []
    for file in files:
        with open(file, encoding="utf-8") as f:
            try:
                data = json.load(f)
                if isinstance(data, list) and data:
                    # Берем винрейт нейронки (6_max_mix или среднее)
                    val = data[-1].get("bb_per_100", 0)
                    all_bb_100.append((file.name, val))
            except:
                pass

    # Проверка на завипание (одинаковые результаты подряд)
    duplicates = 0
    for i in range(1, len(all_bb_100)):
        if all_bb_100[i][1] == all_bb_100[i-1][1]:
            duplicates += 1

    for name, val in all_bb_100:
        report.append(f"{name}: {val:.2f} bb/100")

    report.append(f"\nПредупреждение: обнаружено {duplicates} идентичных результатов подряд.")
    if duplicates > 2:
        report.append("ВНИМАНИЕ! Высокая вероятность того, что сид (Seed) не меняется, и играются одинаковые раздачи!")

    report.append("")
    return report

def analyze_database():
    report = ["### Анализ Базы Данных (Разнообразие оппонентов) ###"]
    db_url = os.getenv("POKER_DATABASE_URL")
    if not db_url:
        report.append("Переменная POKER_DATABASE_URL не установлена.")
        return report

    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from poker.statistics.database.sqlalchemy_models import PlayerModel, PlayerStatisticsModel

        engine = create_engine(db_url)
        Session = sessionmaker(engine)
        session = Session()

        total_players = session.query(PlayerModel).count()
        report.append(f"Всего игроков в базе: {total_players}")

        active_players = session.query(PlayerStatisticsModel).filter(PlayerStatisticsModel.hands > 0).count()
        report.append(f"Активных игроков (сыграли хоть 1 раздачу): {active_players}")

        if active_players < 5 and total_players > 10:
            report.append("ВНИМАНИЕ! В базе много ботов, но играют одни и те же. Проверьте генерацию Seed при посадке за стол.")

        session.close()
    except Exception as e:
        report.append(f"Ошибка при подключении к БД: {e}")

    report.append("")
    return report

def main():
    parser = argparse.ArgumentParser(description="Диагностика здоровья пайплайна машинного обучения.")
    parser.add_argument("--output", default="artifacts/pipeline_health_report.txt", help="Куда сохранить отчет")
    args = parser.parse_args()

    report_lines = [
        "===============================================",
        "   Отчет о здоровье ML Пайплайна Neuro Poker   ",
        "===============================================\n"
    ]

    report_lines.extend(analyze_datasets("models/datasets") or analyze_datasets("datasets"))
    report_lines.extend(analyze_benchmarks("models/artifacts") or analyze_benchmarks("artifacts"))
    report_lines.extend(analyze_database())

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(f"Диагностический отчет сохранен в: {out_path}")

if __name__ == "__main__":
    main()
