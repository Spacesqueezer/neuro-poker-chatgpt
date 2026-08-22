# Vision

Этап: захват окна PokerDom.

Добавлено:
- поиск окна через WinAPI;
- захват только окна игры;
- подготовка к поиску ROI стола.

Установка:

pip install pywin32

Запуск:

python src/poker/vision/window_runner.py

Следующий этап:
определение границ стола внутри окна.
