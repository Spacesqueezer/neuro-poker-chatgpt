# Запуск и обслуживание

[Все документы](../README.md) · [Обучение](LEARNING.md) · [HUD](VISION.md)

Все команды выполняются из корня проекта. Примеры предназначены для PowerShell.

## Окружение

Требуется Python 3.12+. Для нового окружения:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,ml,hud]"
python --version
python -m pip check
```

При последующих запусках достаточно `.\.venv\Scripts\Activate.ps1`.
Без активации можно вызывать `.\.venv\Scripts\python.exe`.
В IDE выбрать этот же интерпретатор.

Extras: `dev` — pytest, coverage, Ruff и mypy; `ml` — PyTorch и Gymnasium;
`hud` — MSS, OpenCV, pytesseract и Pillow. Для одной симуляции достаточно
`python -m pip install -e ".[dev]"`. Tesseract устанавливается отдельно.

## Проверки

```powershell
python -m pytest -q
python -m pytest tests/agents/test_expert_agent.py -q
python -m pytest --cov=poker
python -m ruff check .
python -m ruff format --check .
python -m mypy
```

Общий набор не требует запущенного PostgreSQL. Правила выбора проверок и особенности
`tools/quality_check.py` описаны в [правилах разработки](DEV_RULES.md).

## Ручная игра

```powershell
python tools/manual_hand.py --seed 42
python tools/manual_hand.py --help
```

`--scenario NAME` выбирает готовый сценарий; список доступен через `--help` или
`scenario list` внутри программы.

| Команды | Действие |
| --- | --- |
| `check`, `call`, `fold`, `all-in` / `allin` | Ход текущего игрока |
| `bet N`, `raise N` | Ставка; raise задаёт итоговую цель ставки на текущей улице |
| `state`, `players`, `table` | Состояние раздачи, игроков и физических мест |
| `sitout NAME`, `sitin NAME` | Изменить участие игрока в следующих раздачах |
| `deal` | Следующая раздача |
| `scenario list`, `scenario NAME` | Список и выбор сценария |
| `help`, `quit` / `exit` | Справка и выход |

Завершённые раздачи записываются в `artifacts/hand_history.jsonl`.

## Истории и воспроизведение

```powershell
python tools/hand_history_viewer.py list
python tools/hand_history_viewer.py stats
python tools/hand_history_viewer.py show 5
python tools/hand_history_viewer.py browse 5
python tools/verify_history.py
```

Без аргументов viewer открывает интерактивный просмотр последней раздачи.
Для другого файла у обоих инструментов есть `--file path/to/history.jsonl`;
у verifier — `--hand N` для одной раздачи. Индексы начинаются с 1.

В просмотре: Enter / `n` / `next` — вперёд, `p` / `prev` / `previous` — назад,
`goto N` — перейти, `list` — список, `q` / `quit` / `exit` — выход.

Истории со случайной раздачей и seed проверяются точным воспроизведением.
Сценарии с `seed=None` проходят структурную проверку.
Ошибка воспроизведения даёт ненулевой код возврата.

## Stress и оценка ExpertAgent

```powershell
python tools/stress_poker.py --hands 10000 --seed 42 --players 6 --stack 200
python tools/benchmark_expert.py --sessions 20 --hands-per-session 100 --seed 42 --output artifacts/expert_benchmark.json
```

Stress по умолчанию: 1000 раздач, seed 42, 3 игрока, стек 100.
Проверяются завершение раздач, неотрицательные стеки, сохранение фишек и история.
Это проверка движка, а не силы стратегии.

Expert benchmark поддерживает `--starting-stack`, `--equity-samples` и
`--opponents random calling_station nit maniac tag lag`.
Сравнивать отчёты при одинаковых настройках; учитывать реально сыгранные руки,
ошибки, завершение сессий и bb/100. Победа над эвристиками не доказывает GTO.

## База данных

Для self-play без долговременной статистики сервер БД необязателен.
`db_manager.py` требует `POKER_DATABASE_URL`. Пример для локального SQLite:

```powershell
$env:POKER_DATABASE_URL="sqlite:///poker.db"
python -m alembic -c alembic.ini upgrade head
python tools/db_manager.py init-pool
python tools/db_manager.py stats
```

Для PostgreSQL сначала создать базу на своём сервере и задать URL:

```powershell
$env:POKER_DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/neuro_poker"
python -m alembic -c alembic.ini upgrade head
```

Пароль в примере заменить; специальные символы в URL кодировать.
Переменная задаётся для текущего терминала. Она не создаёт сам сервер или базу.

| Команда | Назначение |
| --- | --- |
| `python -m alembic -c alembic.ini heads` | Последняя доступная ревизия |
| `python -m alembic -c alembic.ini current` | Ревизия подключённой БД |
| `python -m alembic -c alembic.ini upgrade head` | Применить миграции |
| `python -m alembic -c alembic.ini downgrade -1` | Откатить одну миграцию |
| `python -m alembic -c alembic.ini downgrade base` | Удалить схему, созданную миграциями |
| `python tools/db_manager.py init-pool` | Добавить недостающих ботов из пула 100 имён |
| `python tools/db_manager.py stats` | Показать до 20 наиболее активных игроков |
| `python tools/db_manager.py clear` | Удалить игроков, статистику и память из подключённой БД |

`clear` и downgrade удаляют данные; это не команды обычного запуска.
Пул включает 30 TAG, 10 Maniac, 20 Nit, 20 LAG, 10 Calling Station и 10 Random.
Реальные таблицы перечислены в [архитектуре](ARCHITECTURE.md).

Для интеграционного теста PostgreSQL нужна отдельная одноразовая база:
тест сбрасывает схему до `base`, затем применяет миграции.

```powershell
$env:POKER_TEST_DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/neuro_poker_test"
python -m pytest tests/statistics/test_postgres_integration.py -q
```

Не указывать рабочую БД в `POKER_TEST_DATABASE_URL`.

## Указатель инструментов

| Область | Инструменты в `tools/` | Руководство |
| --- | --- | --- |
| Ручная игра, история | `manual_hand.py`, `hand_history_viewer.py`, `verify_history.py` | Этот файл |
| Проверки | `stress_poker.py`, `quality_check.py` | Этот файл и [разработка](DEV_RULES.md) |
| БД | `db_manager.py` | Этот файл |
| Датасеты | `generate_dataset.py`, `import_teacher_dataset.py` | [Обучение](LEARNING.md) |
| Новая модель текущего состояния | `prepare_snapshot_policy.py`, `train_snapshot_policy.py`, `audit_snapshot_policy.py`, `replay_snapshot_advice.py` | [Обучение и офлайн-советник](LEARNING.md) |
| Обучение | `train_imitation.py`, `train_rl.py`, `run_self_play.py`, `rl_orchestrator.py`, `early_stopping_orchestrator.py` | [Обучение](LEARNING.md) |
| Оценка | `benchmark_expert.py`, `benchmark_neural.py`, `run_tournament.py`, `play_vs_model.py`, `pipeline_diagnostics.py` | [Обучение](LEARNING.md) |
| Solver | `benchmark_mccfr.py`, `export_mccfr_strategy.py`, `export_teacher_records.py`, `evaluate_solver_policy.py`, `smoke_solver_artifacts.py` | [Обучение](LEARNING.md) |
| HUD | `run_hud.py`, `hud_players.py` | [HUD](VISION.md) |

`manual_scenarios.py` содержит сценарии для ручного режима, а не отдельную команду запуска.
Для CLI на argparse используйте `--help`; графические инструменты могут запускаться сразу.

Статистика живого HUD хранится в `data/hud/players.sqlite3` без Postgres.
Перенос через кнопку «Копия БД» и правила счётчика описаны в [HUD](VISION.md).
