# Vision — полный rewrite card detector v1

Это не очередной тюнинг старых thresholds. `CardDetector` переписан целиком.

## Что было неправильно

Старый подход считал каждую карту независимым белым прямоугольником:

```text
threshold -> contour -> width/height/aspect/fill -> CardBox
```

Это ломалось сразу в нескольких реальных сценариях PokerDom:

- chips перекрыли одну board card;
- player panel закрыл низ hole cards;
- contour одной карты временно исчез;
- две светлые области слиплись;
- на turn detector увидел карты `1, 2, 4`, потерял `3` и вернул три boxes.

Последний случай особенно плох: список сжимается, индексы карт сдвигаются,
а street остаётся `flop`, хотя четвёртая карта уже существует.

## Новый board detector

Board теперь рассматривается как **геометрическая решётка из 5 slots**.

### Flop

Первый устойчивый flop используется для калибровки:

```text
card width
card height
first slot X/Y
pitch между картами
```

Требуется регулярная горизонтальная тройка.

### Turn / river

После калибровки количество карт больше НЕ равно количеству contours.

Следующий street проверяется непосредственно в следующем canonical slot:

```text
slot 4 -> есть card evidence -> turn
slot 5 -> есть card evidence -> river
```

Если на turn detector физически видит:

```text
1, 2, _, 4
```

он всё равно возвращает:

```text
slot1, slot2, slot3, slot4
```

Потерянный slot3 восстанавливается из сохранённой геометрии. Поэтому OCR
продолжает читать правильные координаты, а street становится `turn`.

Board geometry сбрасывается только после нескольких последовательных кадров,
в которых реально исчез весь board.

## Partial occlusion

Карта больше не обязана иметь полный белый contour.

Candidate принимается даже если видимо примерно 38% высоты. При частичном
перекрытии полный CardBox восстанавливается канонического размера.

Это предназначено и для:

```text
board card + chips
```

и для:

```text
hole card + player panel
```

## HERO cards

Для HERO вообще не нужен contour полного прямоугольника.

После нахождения hero panel:

```text
1. Берётся canonical card size.
2. Строятся два ожидаемых соседних slots над panel.
3. Каждый slot локально двигается на несколько пикселей, максимизируя
   card evidence в верхней части.
4. Нижняя часть может быть перекрыта player panel.
```

Если board уже был, HERO автоматически использует реально измеренный размер
board cards. На preflop размер оценивается от table scale.

## White mask

Большой `MORPH_CLOSE`, который мог склеивать соседние карты, удалён.

Осталась только лёгкая обработка:

```text
OPEN  2x2 x1
CLOSE 3x3 x1
```

## Public API

Интерфейс сохранён:

```python
CardDetector.detect_board(table_frame)
CardDetector.detect_hero(table_frame, hero_panel)
CardDetector.signature(cards)
crop_card(frame, card)
```

Поэтому patch не требует переделывать runner.

## Файл

Patch намеренно заменяет только:

```text
src/poker/vision/detection/cards.py
```

Это позволяет наложить его поверх commit, который пользователь сейчас делает,
не затрагивая остальной Vision pipeline.
