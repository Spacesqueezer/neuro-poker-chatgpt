# Инструкция пользователя

Этот файл — практическая шпаргалка по запуску Neuro Poker. Здесь собраны команды, которые нужны для повседневной работы с проектом: тесты, ручная игра, истории раздач, stress-тесты, benchmark ExpertAgent, генерация датасетов, миграции БД, snapshots и применение NeuroPatch.

Все команды ниже предполагают запуск из корня проекта.

## 1. Подготовка окружения

Проект требует Python 3.12 или новее.

Создание виртуального окружения в Windows:

```text
python -m venv .venv
.venv\Scripts\activate
```

Установка проекта и dev-зависимостей:

```text
python -m pip install -e ".[dev]"
```

Если нужны ML-зависимости:

```text
python -m pip install -e ".[dev,ml]"
```

Проверить установленный Python:

```text
python --version
```

## 2. Быстрая проверка проекта

Запустить все тесты:

```text
python -m pytest -q
```

Запустить один файл тестов:

```text
python -m pytest tests/poker/test_expert_agent.py -q
```

Запустить один конкретный тест:

```text
python -m pytest tests/poker/test_expert_agent.py::test_expert_agent_always_returns_legal_decision -q
```

Полная проверка качества:

```text
python tools/quality_check.py
```

Она последовательно запускает:

```text
ruff check .
ruff format --check .
pyright
pytest --cov
```

Если нужен только Ruff:

```text
ruff check .
ruff format --check .
```

## 3. Ручная игра и отладка раздачи

Запуск случайной ручной раздачи:

```text
python tools/manual_hand.py
```

Запуск с фиксированным seed:

```text
python tools/manual_hand.py --seed 42
```

Запуск готового сценария:

```text
python tools/manual_hand.py --scenario NAME
```

Список доступных сценариев можно посмотреть уже внутри программы:

```text
scenario list
```

Аргументы запуска:

```text
--scenario NAME
```

Выбирает сценарий. По умолчанию используется `default`.

```text
--seed N
```

Фиксирует seed для воспроизводимой случайной раздачи.

Команды внутри ручного режима:

```text
check
call
fold
all-in
allin
bet N
raise N
state
players
table
sitout NAME
sitin NAME
deal
scenario list
scenario NAME
help
quit
exit
```

`bet N` — ставка размером N.

`raise N` — raise-to до N, то есть N является итоговой целью ставки игрока на текущей улице.

`state` — показать текущее состояние стола.

`players` — показать игроков.

`table` — показать физические места и статусы.

`sitout NAME` / `sitin NAME` — вывести игрока из игры или вернуть его.

`deal` — начать следующую руку на текущем столе.

Завершённые истории ручных раздач сохраняются в:

```text
artifacts/hand_history.jsonl
```

## 4. Просмотр истории раздач

Интерактивный просмотр последней истории:

```text
python tools/hand_history_viewer.py
```

То же самое явно:

```text
python tools/hand_history_viewer.py browse
```

Показать список всех записанных рук:

```text
python tools/hand_history_viewer.py list
```

Показать статистику файла историй:

```text
python tools/hand_history_viewer.py stats
```

Показать конкретную руку по номеру:

```text
python tools/hand_history_viewer.py show 5
```

Начать интерактивный просмотр с пятой руки:

```text
python tools/hand_history_viewer.py browse 5
```

Использовать другой JSONL-файл:

```text
python tools/hand_history_viewer.py list --file path/to/history.jsonl
```

Команды внутри `browse`:

```text
Enter
n
next
p
prev
previous
goto N
list
q
quit
exit
```

## 5. Проверка replay историй

Проверить стандартный файл:

```text
python tools/verify_history.py
```

Проверить другой файл:

```text
python tools/verify_history.py --file path/to/history.jsonl
```

Проверить одну руку по номеру:

```text
python tools/verify_history.py --hand 3
```

Одновременно другой файл и конкретную руку:

```text
python tools/verify_history.py --file path/to/history.jsonl --hand 3
```

Seed-based истории проверяются exact replay. Scripted histories проходят structural verification.

Код возврата будет ненулевым, если найдены ошибки replay.

## 6. Stress-тест движка

Базовый запуск:

```text
python tools/stress_poker.py
```

По умолчанию:

```text
1000 рук
seed = 42
3 игрока
stack = 100
```

Типичный большой прогон:

```text
python tools/stress_poker.py --hands 10000 --seed 42
```

Все аргументы:

```text
--hands N
```

Количество рук. Должно быть больше нуля.

```text
--seed N
```

Базовый seed.

```text
--players N
```

Количество игроков. Минимум 2.

```text
--stack N
```

Стартовый стек каждого игрока. При стандартных блайндах 1/2 минимум 2.

Пример:

```text
python tools/stress_poker.py --hands 50000 --seed 123 --players 6 --stack 200
```

Stress runner проверяет завершение рук, отсутствие отрицательных стеков, conservation chips, корректную историю и отсутствие дубликатов видимых карт.

Это проверка движка, а не оценка силы агента.

## 7. Benchmark ExpertAgent

Быстрый benchmark:

```text
python tools/benchmark_expert.py
```

По умолчанию Expert играет отдельные серии против:

```text
random
calling_station
nit
```

Аргументы:

```text
--sessions N
```

Количество независимых Arena-сессий на каждого соперника. По умолчанию 20.

```text
--hands-per-session N
```

Максимальное количество рук в одной сессии. По умолчанию 100.

```text
--starting-stack N
```

Стартовый стек. По умолчанию 200.

```text
--seed N
```

Базовый seed. По умолчанию 42.

```text
--equity-samples N
```

Количество Monte-Carlo rollout'ов ExpertAgent на одно решение. По умолчанию 300.

Больше значение обычно даёт более стабильную оценку equity, но сильнее замедляет расчёт.

```text
--opponents NAME [NAME ...]
```

Каких соперников использовать.

Допустимые значения:

```text
random
calling_station
nit
```

Пример:

```text
python tools/benchmark_expert.py --sessions 50 --hands-per-session 100 --equity-samples 500 --opponents calling_station nit
```

Сохранить JSON-отчёт в файл:

```text
python tools/benchmark_expert.py --output artifacts/expert_benchmark.json
```

В результате выводятся, среди прочего:

```text
hands
failed_hands
expert_profit
bb_per_100
showdowns
uncontested_wins
completion_rate
```

Для сравнения изменений ExpertAgent желательно использовать одинаковые параметры и одинаковый seed.

## 8. Генерация обучающего датасета

Базовый пример:

```text
python tools/generate_dataset.py --output datasets/expert_v1
```

`--output` обязателен.

По умолчанию используются:

```text
hands = 10000
seed = 42
starting_stack = 100
validation_fraction = 0.1
agents = expert calling_station nit
teacher = expert
expert_equity_samples = 300
```

Аргументы:

```text
--output PATH
```

Каталог результата.

```text
--hands N
```

Количество запрошенных Arena-рук.

```text
--seed N
```

Seed генерации.

```text
--starting-stack N
```

Стартовый стек.

```text
--validation-fraction X
```

Доля validation. Например `0.1` означает 10%.

```text
--agents NAME [NAME ...]
```

Состав стола.

Допустимые агенты:

```text
expert
random
calling_station
nit
```

```text
--teacher NAME
```

Решения какого игрока писать в обучающий датасет.

Обычно:

```text
--teacher expert
```

```text
--expert-equity-samples N
```

Количество Monte-Carlo samples для ExpertAgent.

Пример:

```text
python tools/generate_dataset.py ^
  --output datasets/expert_100k ^
  --hands 100000 ^
  --seed 42 ^
  --starting-stack 200 ^
  --validation-fraction 0.1 ^
  --agents expert calling_station nit ^
  --teacher expert ^
  --expert-equity-samples 500
```

В PowerShell вместо `^` удобнее использовать обратную кавычку или записать команду в одну строку.

Генератор создаёт в указанной папке:

```text
dataset.jsonl
train.jsonl
validation.jsonl
manifest.json
```

`dataset.jsonl` — сырой полный набор samples.

`train.jsonl` — обучающая часть.

`validation.jsonl` — validation split.

`manifest.json` — параметры генерации и анализ датасета.

Генерация аварийно завершается, если Arena сообщает failed hands.

## 8.1. MCCFR benchmark restricted Hold'em

Этот benchmark — отдельная opt-in проверка качества и скорости solver'а. Он намеренно не запускается обычным `pytest`, потому что увеличение числа MCCFR-итераций быстро делает проверку тяжёлой.

Канонический небольшой equal-stack baseline:

```text
python tools/benchmark_mccfr.py --scenario equal --iterations 100 --seed 42 --output artifacts/mccfr_equal_baseline.json
```

Канонический asymmetric-stack baseline:

```text
python tools/benchmark_mccfr.py --scenario asymmetric --iterations 100 --seed 42 --output artifacts/mccfr_asymmetric_baseline.json
```

Сценарии фиксированы и воспроизводимы:

```text
equal       -> starting_stacks = [20, 20]
asymmetric  -> starting_stacks = [8, 20]
```

Аргументы:

```text
--scenario NAME
```

Выбор конфигурации стеков. Допустимые значения: `equal` и `asymmetric`. По умолчанию `equal`.

```text
--iterations N
```

Количество MCCFR-итераций финального checkpoint. Должно быть больше 1. По умолчанию 100.

```text
--seed N
```

Seed для воспроизводимого sampling. По умолчанию 42.

```text
--output PATH
```

Необязательный путь для сохранения того же JSON-отчёта, который печатается в stdout.

В отчёте есть:

```text
benchmark_version
scenario
starting_stacks
iterations
seed
first_checkpoint_iterations
information_sets
strategy_distance_from_first_checkpoint
first_checkpoint_seconds
final_seconds
final_iterations_per_second
```

Для сравнения solver-изменений используй одинаковые `--scenario`, `--iterations` и `--seed`. `scenario`, `starting_stacks`, `information_sets` и `strategy_distance_from_first_checkpoint` являются основными сравнительными конфигурационными/quality-полями. Время и throughput зависят от компьютера, поэтому их нужно сравнивать как performance baseline на одной и той же машине, а не как жёсткий тестовый порог.

Большие convergence-прогоны запускаются вручную через этот tool и не должны переноситься в обычный pytest.

## 9. NeuroPatch

Обычное применение скачанного патча:

```text
python tools/neuropatch.py
```

Важно: NeuroPatch автоматически ищет в пользовательской папке:

```text
Downloads
```

все файлы:

```text
*.npatch.json
```

и выбирает самый свежий по времени изменения.

Поэтому перед запуском полезно убедиться, что нужный патч действительно самый новый. Старые `.npatch.json` лучше переносить из Downloads после применения.

Проверка без применения:

```text
python tools/neuropatch.py --dry-run
```

`--dry-run` валидирует структуру патча и состояние Git, но не изменяет файлы и не запускает операции патча.

Принудительный запуск при dirty working tree:

```text
python tools/neuropatch.py --force
```

Использовать `--force` следует только когда точно понятно, зачем это нужно. Обычный рабочий процесс требует чистый Git.

Успешный патч:

- делает backup затрагиваемых файлов;
- применяет операции;
- запускает validation commands из патча;
- записывает историю;
- автоматически создаёт Git commit, если `git.auto_commit` не отключён.

При ошибке NeuroPatch выполняет rollback.

После завершения NeuroPatch пытается воспроизвести локальный звуковой сигнал из папки `sound` в корне проекта:

```text
sound/alarm_success.mp3
sound/alarm_error.mp3
```

`alarm_success.mp3` воспроизводится после успешного результата, `alarm_error.mp3` — после ошибки. На Windows воспроизведение запускается в отдельном скрытом процессе: NeuroPatch не ждёт окончания MP3 и завершает работу сразу после отчёта. Звук является необязательным: если файл отсутствует или воспроизведение не удалось, результат патча от этого не меняется. Папка `sound/` локальная и игнорируется Git.

Итоговый JSON-отчёт содержит `duration_seconds` — полное время выполнения транзакции в секундах, включая применение операций, validation и создание Git commit.

Транзакции и история хранятся вне проекта:

```text
%USERPROFILE%\.neuropatch\<project_name>\transactions
%USERPROFILE%\.neuropatch\<project_name>\history.json
```

Перед применением патча полезно проверить:

```text
git status
```

После успешного применения:

```text
git status
git log -1 --oneline
git push
```

После JSON-отчёта успешный NeuroPatch также печатает строку `SUCCESS HANDOFF`. Она сформулирована как готовая команда следующему AI-сеансу и уже предполагает, что успешный commit запушен.

Обычный цикл после успеха:

```text
git push
```

После этого достаточно отправить нейросети последнюю строку `SUCCESS HANDOFF`. Полный успешный JSON-отчёт пересылать не обязательно, если дополнительная диагностика не нужна. Получив handoff, нейросеть должна перечитать свежую репу, заново свериться с `docs/DEV_RULES.md` и `docs/PROJECT_STATE.md`, продолжить записанный next step и сразу выдать следующий `.npatch.json` файл.

## 10. Snapshot проекта

Создать компактный snapshot:

```text
python tools/snapshot.py
```

Аргументов у команды сейчас нет.

Snapshots создаются в:

```text
tools/snapshots/
```

Хранятся последние 5 архивов.

Из snapshot исключаются тяжёлые и генерируемые данные, среди прочего:

```text
.git
.venv
artifacts
datasets
models
weights
checkpoints
logs
cache
```

Snapshot предназначен для передачи состояния исходников и документации, а не обучающих данных.

## 11. PostgreSQL и Alembic

Alembic использует URL БД из переменной окружения:

```text
POKER_DATABASE_URL
```

Пример для PowerShell:

```text
$env:POKER_DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/neuro_poker"
```

Пример для cmd.exe:

```text
set POKER_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/neuro_poker
```

Показать текущую head-миграцию:

```text
python -m alembic -c alembic.ini heads
```

Показать текущую применённую revision:

```text
python -m alembic -c alembic.ini current
```

Обновить БД до последней миграции:

```text
python -m alembic -c alembic.ini upgrade head
```

Откатить одну миграцию:

```text
python -m alembic -c alembic.ini downgrade -1
```

Полный откат к base:

```text
python -m alembic -c alembic.ini downgrade base
```

С реальной рабочей БД downgrade следует выполнять только осознанно.

## 12. PostgreSQL integration test

Обычный pytest не требует запущенного PostgreSQL: integration test будет пропущен.

Для проверки настоящего PostgreSQL задаётся отдельная disposable test database:

PowerShell:

```text
$env:POKER_TEST_DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/neuro_poker_test"
python -m pytest tests/poker/test_postgres_integration.py -q
```

cmd.exe:

```text
set POKER_TEST_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/neuro_poker_test
python -m pytest tests/poker/test_postgres_integration.py -q
```

Использовать рабочую БД для integration test нельзя: тестовая база должна быть одноразовой.

## 13. Полезный рабочий цикл

После получения нового патча:

```text
git status
python tools/neuropatch.py
git status
git log -1 --oneline
git push
```

Перед серьёзным изменением ExpertAgent:

```text
python tools/benchmark_expert.py --sessions 50 --hands-per-session 100 --seed 42 --equity-samples 300 --output artifacts/expert_before.json
```

После изменения — та же команда, но другой output:

```text
python tools/benchmark_expert.py --sessions 50 --hands-per-session 100 --seed 42 --equity-samples 300 --output artifacts/expert_after.json
```

Для проверки движка:

```text
python -m pytest -q
python tools/stress_poker.py --hands 10000 --seed 42
python tools/verify_history.py
```

Для генерации данных учителя:

```text
python tools/generate_dataset.py --output datasets/expert_v1 --hands 100000 --teacher expert
```

## 14. Что сейчас является чем

`manual_hand.py` — ручная отладка игровых правил.

`hand_history_viewer.py` — просмотр записанных рук.

`verify_history.py` — проверка replay.

`stress_poker.py` — проверка надёжности движка.

`benchmark_expert.py` — измерение силы текущего ExpertAgent против baseline-агентов.

`generate_dataset.py` — создание обучающего датасета из реальных решений агентов.

`quality_check.py` — полный набор статических проверок и тестов.

`snapshot.py` — компактный архив исходников и документации.

`neuropatch.py` — транзакционное применение патчей.

Alembic — управление схемой БД.

## 15. Как поддерживать этот файл

Этот файл является пользовательской документацией проекта.

При добавлении или изменении:

- CLI-команды;
- аргумента командной строки;
- интерактивной команды;
- нового инструмента в `tools/`;
- нового формата output;
- нового стандартного workflow;
- переменной окружения, необходимой пользователю;
- способа запуска тестов, benchmark, генерации данных, миграций или обучения;

`docs/USER_GUIDE_RU.md` должен быть обновлён тем же патчем.

Если функция существует только как внутренний Python API и не требует действий пользователя, добавлять её сюда необязательно.
