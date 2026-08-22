# Vision Anchor v1

Добавляет первый реальный этап зрения.

## Что есть

- захват экрана через mss;
- поиск PokerDom anchor через OpenCV template matching;
- консольный вывод состояния.

Пример:

[VISION] Started
[CONFIG] Hero: spacesqueezer
[SEARCH] Anchor not found
[ANCHOR] Found score=0.91 x=412 y=183

## Установка

pip install opencv-python mss numpy

## Требование

Нужен файл:

assets/pokerdom_anchor.png

Это небольшой шаблон элемента интерфейса PokerDom.
