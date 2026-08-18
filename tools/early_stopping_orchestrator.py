import argparse
import subprocess
import json
from pathlib import Path
import sys
import shutil

def run_command(cmd, description):
    print(f"\n[{description}] Выполняется: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"[{description}] Ошибка! Процесс завершился с кодом {result.returncode}")
        sys.exit(result.returncode)

def main():
    parser = argparse.ArgumentParser(description="Умный оркестратор обучения RL с ранней остановкой (Early Stopping).")
    parser.add_argument("--pool-dir", required=True, help="Директория для пула моделей (где идет обучение)")
    parser.add_argument("--max-iterations", type=int, default=50, help="Максимальное количество итераций обучения")
    parser.add_argument("--hands", type=int, default=1000, help="Количество раздач для Self-Play за итерацию")
    parser.add_argument("--epochs", type=int, default=5, help="Количество эпох обучения RL за итерацию")
    parser.add_argument("--eval-hands", type=int, default=1000, help="Дистанция (кол-во раздач) для бенчмарка")
    parser.add_argument("--patience", type=int, default=5, help="Сколько итераций без улучшений ждать до остановки (Early Stopping)")
    args = parser.parse_args()

    pool_dir = Path(args.pool_dir)
    pool_dir.mkdir(parents=True, exist_ok=True)

    ready_agents_dir = Path("ready_agents")
    ready_agents_dir.mkdir(exist_ok=True)

    log_file = ready_agents_dir / "best_models_log.md"
    if not log_file.exists():
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("# Журнал лучших моделей (Лучшие версии агентов)\n\n")
            f.write("Этот файл содержит подробные комментарии о моделях, которые показали наивысший винрейт на этапе оценки.\n\n")

    # Ищем базовую модель в пуле
    models = sorted(pool_dir.glob("*.pt"))
    if not models:
        print(f"Ошибка: Не найдено ни одной модели в {pool_dir}. Сначала нужно добавить базовую модель (например, policy_v0.pt).")
        sys.exit(1)

    current_model = models[-1]

    best_winrate = -float('inf')
    iterations_without_improvement = 0

    opponents_to_eval = "tag maniac random"

    print("================================================================")
    print(" Запуск умного оркестратора обучения (Early Stopping Tracker)")
    print("================================================================\n")

    for iteration in range(1, args.max_iterations + 1):
        print(f"\n========== ИТЕРАЦИЯ {iteration} ==========")

        # 1. Генерация данных (Self-Play)
        dataset_path = pool_dir.parent / "datasets" / f"self_play_iter_{iteration}.jsonl"
        dataset_path.parent.mkdir(parents=True, exist_ok=True)
        run_command([
            sys.executable, "tools/run_self_play.py",
            "--current-model", str(current_model),
            "--pool-dir", str(pool_dir),
            "--output", str(dataset_path),
            "--hands", str(args.hands)
        ], "Генерация раздач (Self-Play)")

        # 2. Обучение (RL Policy Gradient)
        new_model_path = pool_dir / f"policy_v{iteration}.pt"
        run_command([
            sys.executable, "tools/train_rl.py",
            "--train", str(dataset_path),
            "--base-model", str(current_model),
            "--output", str(new_model_path),
            "--epochs", str(args.epochs)
        ], "Обучение нейросети (RL)")

        # 3. Оценка (Evaluate)
        benchmark_out = pool_dir.parent / "artifacts" / f"benchmark_iter_{iteration}.json"
        benchmark_out.parent.mkdir(parents=True, exist_ok=True)
        run_command([
            sys.executable, "tools/benchmark_neural.py",
            "--model", str(new_model_path),
            "--opponents", "tag", "maniac", "random",
            "--hands", str(args.eval_hands),
            "--output", str(benchmark_out)
        ], "Бенчмарк против оппонентов")

        # 4. Анализ результатов (Early Stopping)
        try:
            with open(benchmark_out, "r", encoding="utf-8") as f:
                results = json.load(f)
        except Exception as e:
            print(f"Ошибка при чтении результатов бенчмарка: {e}")
            continue

        total_bb_100 = 0
        opponents_count = len(results)

        details = []
        for r in results:
            opp = r.get("opponent", "unknown")
            bb100 = r.get("bb_per_100", 0)
            total_bb_100 += bb100
            details.append(f"- Против **{opp}**: {bb100:.2f} bb/100")

        avg_bb_100 = total_bb_100 / opponents_count if opponents_count > 0 else 0

        print(f"\n[Анализ] Средний винрейт за итерацию: {avg_bb_100:.2f} bb/100")

        if avg_bb_100 > best_winrate:
            print(f"[Анализ] ✨ НОВЫЙ РЕКОРД! Винрейт вырос с {best_winrate:.2f} до {avg_bb_100:.2f}.")
            best_winrate = avg_bb_100
            iterations_without_improvement = 0

            # Сохранение лучшей модели
            best_model_name = f"best_model_iter_{iteration}_bb_{avg_bb_100:.1f}.pt"
            best_model_dest = ready_agents_dir / best_model_name
            shutil.copy(new_model_path, best_model_dest)
            print(f"[Анализ] Модель сохранена в {best_model_dest}")

            # Запись в лог
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"### Итерация {iteration} (Модель: `{best_model_name}`)\n")
                f.write(f"**Средний винрейт (bb/100):** {avg_bb_100:.2f}\n")
                f.write("**Результаты по оппонентам:**\n")
                f.write("\n".join(details) + "\n\n")
                f.write("> *Автоматический комментарий:* Модель показала рекордный результат. Является кандидатом для использования в реальных играх.\n\n---\n\n")

        else:
            iterations_without_improvement += 1
            print(f"[Анализ] Нет улучшений. Текущий рекорд: {best_winrate:.2f}. Итераций без улучшений: {iterations_without_improvement}/{args.patience}")

        # Промоут модели (для следующей итерации используем текущую обученную, чтобы бот продолжал развиваться)
        current_model = new_model_path

        if iterations_without_improvement >= args.patience:
            print("\n" + "="*60)
            print("🛑 СРАБОТАЛА РАННЯЯ ОСТАНОВКА (EARLY STOPPING) 🛑")
            print(f"Винрейт не растет уже {args.patience} итераций подряд.")
            print(f"Сеть, скорее всего, достигла своего максимума (потолка) при текущей архитектуре.")
            print(f"Лучшая модель сохранена в папке {ready_agents_dir}")
            print("Рекомендуется протестировать лучшую модель из папки ready_agents в бою!")
            print("="*60 + "\n")
            break

    if iterations_without_improvement < args.patience:
        print("\nОбучение завершилось по достижении максимального числа итераций.")
        print(f"Лучшая модель и ее статистика лежат в {ready_agents_dir}")

if __name__ == "__main__":
    main()
