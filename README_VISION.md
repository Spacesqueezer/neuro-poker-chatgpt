# Vision — HandState + card voting v1

Следующий слой над уже работающим card detector.

## Что исправляет

Однокадровое распознавание вроде:

```text
5h
5h
Jh
5h
```

больше не должно превращать runtime state в `Jh`.

Первый валидный read принимается сразу, но смена уже подтверждённой карты
требует нескольких голосов:

```text
board card switch: 3 votes
hero card switch:  4 votes
```

## Board монотонный

В рамках одной руки допускается только:

```text
0 -> 3 -> 4 -> 5
preflop -> flop -> turn -> river
```

Если detector на turn временно показывает только 3 карты, tracker не
откатывается на flop и не сдвигает card slots.

Если одна из четырёх карт временно потеряна, более короткий OCR sample
игнорируется целиком.

## Новая рука

Board очищается не по одному пустому кадру, а после серии из 7 detector scans
без board boxes. Resize/re-lock стола не считается новой рукой.

## Важное изменение runner

Раньше при любом изменении card geometry выполнялось:

```text
card_state.reset_board()
card_state.reset_hero()
```

То есть voting уничтожался именно тогда, когда он был нужнее всего.

Теперь signature change меняет только geometry boxes. Hand/card state живёт
отдельно.

Патч меняет:

```text
src/poker/vision/runner.py
src/poker/vision/tracking/card_state.py
src/poker/vision/tracking/hand_state.py
```

`cards.py` не трогается — текущий рабочий partial-occlusion detector остаётся.
