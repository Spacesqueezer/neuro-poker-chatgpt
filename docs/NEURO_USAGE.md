# Руководство по обучению нейросети (Neuro Poker)

Этот документ описывает полный цикл создания, обучения и тестирования нейросетевых агентов (NeuralAgent) в проекте Neuro Poker. Здесь также описаны шаги по работе с базой данных (PostgreSQL), которая используется для хранения профилей игроков и их памяти друг о друге.

---

## 1. Подготовка Базы Данных (PostgreSQL)

Вся статистика игроков и приватная память агентов (Opponent Memory) хранится в БД.

**1. Установка PostgreSQL под Windows:**
Если у вас ещё нет базы данных:
1. Скачайте установщик с официального сайта: https://www.postgresql.org/download/windows/
2. При установке запомните пароль, который вы задаёте для суперпользователя `postgres`.
3. Оставьте стандартный порт `5432`.
4. В конце установки вы можете открыть **pgAdmin 4** (идет в комплекте).

**2. Создание базы данных:**
1. Откройте **pgAdmin 4**, подключитесь к серверу (введя пароль от `postgres`).
2. Нажмите правой кнопкой мыши на `Databases` -> `Create` -> `Database...`
3. Введите название: `neuro_poker` и нажмите `Save`.

**3. Настройка URL БД:**
Теперь нужно сообщить нашему коду, как подключиться к базе. В адресе подключения замените `password` на тот пароль, который вы придумали при установке.

Установите переменную окружения `POKER_DATABASE_URL`.

```powershell
# Для Windows (PowerShell)
$env:POKER_DATABASE_URL="postgresql+psycopg://postgres:ВАШ_ПАРОЛЬ@localhost:5432/neuro_poker"
```

```cmd
# Для Windows (CMD)
set POKER_DATABASE_URL=postgresql+psycopg://postgres:ВАШ_ПАРОЛЬ@localhost:5432/neuro_poker
```

```bash
# Для Linux/macOS
export POKER_DATABASE_URL="postgresql+psycopg://postgres:ВАШ_ПАРОЛЬ@localhost:5432/neuro_poker"
```

*(Опционально: если хотите гонять тесты, создайте в pgAdmin базу `neuro_poker_test` и задайте аналогичную переменную `POKER_TEST_DATABASE_URL`)*.

**4. Инициализация схемы (Миграции Alembic):**
Проект использует систему миграций Alembic для управления таблицами. Чтобы создать все необходимые таблицы в вашей свежей базе `neuro_poker`, выполните в терминале (где установлена переменная среды):
```bash
python -m alembic -c alembic.ini upgrade head
```
Если команда отработала без ошибок, база данных готова к сбору памяти об оппонентах!

**5. Генерация пула ботов (6-max PBT):**
Для того чтобы нейросеть обучалась играть за 6-макс столом против разных стилей оппонентов, в базу данных нужно занести "пул" постоянных ботов. В проекте есть скрипт для управления БД. Выполните:
```bash
python tools/db_manager.py init-pool
```
Это создаст 100 ботов различных стилей (TAG, LAG, Maniac, Nit, Station, Random) в базе данных. Позже вы можете смотреть статистику их винрейтов с помощью:
```bash
python tools/db_manager.py stats
```

---

## 2. Имитационное обучение (Imitation Learning)

Перед тем как сеть начнёт играть сама, ей нужна базовая стратегия. Мы клонируем логику солвера (MCCFR).

**1. Генерация стратегии солвера (Solver Artifacts):**
Сначала мы обучаем солвер находить оптимальную стратегию и экспортируем её.
```bash
python tools/export_mccfr_strategy.py --scenario equal --iterations 100 --seed 42 --output artifacts/mccfr_equal_strategy.json
```

**2. Конвертация стратегии в записи учителя (Teacher Records):**
Сырая стратегия солвера содержит много внутренней информации. Этот шаг извлекает только решённые вероятности действий и переводит их в промежуточный формат записей учителя.
```bash
python tools/export_teacher_records.py --strategy artifacts/mccfr_equal_strategy.json --output artifacts/mccfr_equal_teacher_records.json
```

**3. Создание обучающего датасета:**
Этот скрипт берёт записи учителя и переводит узлы дерева игры в векторы наблюдений (тензоры) `LearningSample`, готовые для нейросети.
```bash
python tools/import_teacher_dataset.py --input artifacts/mccfr_equal_teacher_records.json --output datasets/teacher_samples.jsonl
```

**4. Обучение сети (Supervised Learning):**
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

## 4. Оркестратор полного цикла (Умное обучение с Early Stopping)

Вместо ручного запуска команд из пункта 3, используйте "Умный оркестратор" (`early_stopping_orchestrator.py`). Он будет генерировать датасеты, обучать сеть, автоматически тестировать её против разных стилей оппонентов (TAG, Maniac, Random) и останавливать обучение, когда нейросеть достигнет своего "потолка" (перестанет улучшать винрейт).

**Рекомендуемая команда для стабильного обучения (6-max PBT):**
```bash
python tools/early_stopping_orchestrator.py --pool-dir models/pool --max-iterations 50 --hands 10000 --epochs 3 --patience 5 --table-size 6
```
*Важно: перед запуском оркестратора в папке `models/pool` должна лежать хотя бы одна стартовая модель (например, обученная через Imitation Learning).*
*Также важно: для 6-max обучения база данных должна быть инициализирована командой `python tools/db_manager.py init-pool`.*

### Рекомендуемые параметры:
* `--hands 10000`: Количество раздач для Self-Play. Значения 1000 слишком мало из-за высокой покерной дисперсии. Рекомендуется от 5000 до 10000.
* `--epochs 3`: Количество проходов (эпох) по собранному датасету. Рекомендуется 2-3, чтобы нейросеть не "зазубривала" одни и те же раздачи.
* `--patience 5`: Количество итераций без улучшения винрейта перед остановкой (Early Stopping).
* `--table-size 6`: Запускает обучение в формате 6-max стола, где модель играет против своих прошлых версий и различных эвристических ботов (Population-Based Training).

### Папка ready_agents/
После каждой успешной итерации (если побит прошлый рекорд по винрейту), оркестратор копирует модель в папку `ready_agents/`. Там же создается файл `best_models_log.md` с подробным описанием (на русском языке), против кого и с каким счетом эта модель победила. Нейросеть также получает доступ к статистике оппонентов благодаря флагу `--profile-scope combined`, что позволяет ей применять эксплуатационные стратегии.

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
