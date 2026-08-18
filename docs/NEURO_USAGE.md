# Руководство по обучению нейросети (Neuro Poker)

Этот документ описывает полный цикл создания, обучения и тестирования нейросетевых агентов (NeuralAgent) в проекте Neuro Poker. Здесь также описаны шаги по работе с базой данных (PostgreSQL), которая используется для хранения профилей игроков и их памяти друг о друге.

---

## 1. Подготовка Базы Данных (PostgreSQL)

Вся статистика игроков и приватная память агентов (Opponent Memory) хранится в БД.

**1. Настройка URL БД:**
Установите переменную окружения `POKER_DATABASE_URL` (и `POKER_TEST_DATABASE_URL` для тестов).

```powershell
# Для Windows (PowerShell)
$env:POKER_DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/neuro_poker"
```

```cmd
# Для Windows (CMD)
set POKER_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/neuro_poker
```

```bash
# Для Linux/macOS
export POKER_DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/neuro_poker"
```

**2. Инициализация схемы (Миграции):**
Проект использует Alembic. Чтобы создать все таблицы, выполните:
```bash
python -m alembic -c alembic.ini upgrade head
```

---

## 2. Имитационное обучение (Imitation Learning)

Перед тем как сеть начнёт играть сама, ей нужна базовая стратегия. Мы клонируем логику солвера (MCCFR).

**1. Генерация данных учителя (Solver Artifacts):**
```bash
python tools/export_mccfr_strategy.py --scenario equal --iterations 100 --seed 42 --output artifacts/mccfr_equal_strategy.json
```

**2. Конвертация стратегии в обучающий датасет:**
Этот скрипт переводит узлы дерева игры в векторы `LearningSample`.
```bash
python tools/import_teacher_dataset.py --input artifacts/mccfr_equal_strategy.json --output datasets/teacher_samples.jsonl
```

**3. Обучение сети (Supervised Learning):**
Скрипт создаёт PyTorch модель (`PokerPolicyNetwork`) и обучает её попадать в предсказания солвера.
```bash
python tools/train_imitation.py --train datasets/teacher_samples.jsonl --validation datasets/teacher_samples.jsonl --output models/policy_v1.pt --epochs 10 --learning-rate 1e-3
```

---

## 3. Обучение с подкреплением (Reinforcement Learning)

Когда у нас есть базовая модель (`policy_v1.pt`), мы заставляем её играть саму с собой для улучшения стратегии через максимизацию выигрыша.

**1. Сбор датасета через Self-Play:**
Агент играет против своих старых версий (из папки `models/pool`).
```bash
python tools/run_self_play.py --current-model models/policy_v1.pt --pool-dir models/pool --output datasets/self_play_v1.jsonl --hands 1000
```
*Этот скрипт также записывает итоговые изменения фишек (reward).*

**2. Обновление весов (Policy Gradient / REINFORCE):**
Нейросеть дообучается: действия, приведшие к выигрышу фишек, поощряются; к проигрышу — пенализируются.
```bash
python tools/train_rl.py --train datasets/self_play_v1.jsonl --base-model models/policy_v1.pt --output models/policy_v2.pt --epochs 5 --value-weight 0.5 --entropy-weight 0.01
```

---

## 4. Оркестратор полного цикла (Automated RL Loop)

Вместо ручного запуска команд из пункта 3, используйте оркестратор. Он будет генерировать датасеты, обучать сеть, тестировать её и обновлять текущую версию в бесконечном (или заданном) цикле.

```bash
python tools/rl_orchestrator.py --pool-dir models/pool --iterations 10 --hands 1000 --epochs 5
```
*Важно: перед запуском оркестратора в папке `models/pool` должна лежать хотя бы одна стартовая модель (например, обученная через Imitation Learning).*

---

## 5. Обучение на видеокартах NVIDIA (CUDA) под Windows

В проекте используется PyTorch, который по умолчанию может установиться в версии только для CPU. Если у вас установлена видеокарта NVIDIA (например, GeForce RTX 3060/4060/5060 Ti), вы можете значительно ускорить процесс обучения сетей (RL и Imitation).

**1. Проверка поддержки CUDA:**
Сначала убедитесь, что PyTorch видит вашу видеокарту. Запустите в терминале:
```text
python -c "import torch; print(torch.cuda.is_available())"
```
Если выводит `False`, значит у вас установлена версия PyTorch без поддержки GPU.

**2. Установка PyTorch с CUDA под Windows:**
Чтобы установить PyTorch с поддержкой CUDA 12.1 (самая стабильная версия для актуальных драйверов NVIDIA), выполните команду:
```powershell
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```
После завершения установки снова выполните команду проверки. Если выводится `True` — всё настроено верно.

**3. Использование CUDA в скриптах:**
Все скрипты обучения (`tools/train_imitation.py` и `tools/train_rl.py`) написаны так, что они автоматически определяют доступность видеокарты. Никаких дополнительных флагов передавать не нужно.
При запуске вы увидите сообщение:
`Using device: cuda` (если всё хорошо) или `Using device: cpu` (если видеокарта не найдена).

---

## 6. Оценка качества (Benchmarking)

Чтобы понять, насколько сильна стала нейросеть, мы стравливаем её с базовыми жестко-запрограммированными ботами (`random`, `nit`, `calling_station`).

```bash
python tools/benchmark_neural.py --model models/policy_v2.pt --opponents nit calling_station --hands 5000 --output artifacts/neural_benchmark.json
```
Результатом будет JSON с подробной статистикой (включая винрейт `bb/100`). Чем выше винрейт, тем успешнее прошло обучение.
