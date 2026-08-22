# Vision Calibration v1

## Что исправляет

- поиск корня проекта;
- автоматическое определение assets;
- загрузка всех anchor PNG;
- debug окно с текущим захватом экрана.

## Запуск

Из корня neuro_poker:

python src/poker/vision/runner.py

## Ожидаемый вывод

[VISION] Started
[PROJECT] D:\Projects\Python\neuro_poker
[ASSETS] D:\Projects\Python\neuro_poker\assets
[ANCHOR] Templates loaded: 7

## Управление

Q - закрыть окно.

## Назначение

Это этап калибровки.

Перед распознаванием карт и игроков нужно убедиться, что CV:
- видит монитор;
- видит окно PokerDom;
- может найти стабильный anchor.
