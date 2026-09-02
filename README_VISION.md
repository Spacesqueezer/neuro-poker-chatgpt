# Vision — fast HERO + async cards v1

Этот patch исправляет две связанные проблемы:

1. Scanner GUI прыгал примерно 5–12 FPS.
2. HERO мог определяться очень долго, а hole cards почти не искались.

## Почему HERO тормозил

`runner` раньше делал:

```text
panels
→ полный OCR всех игроков
→ найти player.is_hero
→ только после этого detect_hero_cards()
```

Полный OCR — самая дорогая часть player pipeline. Пока он не завершился,
`hero_panel=None`, а значит hole cards вообще не искались.

Теперь добавлен `FastHeroLocator`.

Он:
- сначала удерживает уже известное физическое место HERO;
- если HERO ещё неизвестен, использует готовые full-name templates
  `assets/players/templates/names/spacesqueezer/`;
- это обычное OpenCV сравнение маленьких nickname ROI без Tesseract;
- когда полный OCR всё-таки подтверждает HERO, locator обновляет cache.

То есть рамка HERO и поиск hole cards больше не должны зависеть от скорости
полного OCR всех ников.

## Почему hole cards сверху не находились

Старая `CardDetector.detect_hero()` исходила из предположения:

```text
hole cards находятся по направлению от panel к центру стола
```

На верхнем seat PokerDom рисует hole cards НАД name panel, то есть в обратную
сторону.

Теперь search ROI строится вокруг и главным образом над hero panel, поэтому
работает и для верхнего seat.

## FPS

Из main loop вынесены:
- `detect_board()`;
- `detect_hero()`;
- card template recognition / Tesseract fallback.

Они выполняются worker-потоками.

Также panel detector в steady-state запускается реже:

```text
1.6 сек вместо 1.0 сек
```

Количество workers увеличено с 2 до 4, чтобы slow nickname OCR не блокировал
card geometry worker.

## Ожидаемый эффект

- dashboard должен стать существенно ровнее;
- HERO должен появляться почти сразу после panels, если есть full-name template
  `spacesqueezer`;
- после первого подтверждённого OCR HERO seat удерживается по физической позиции;
- hole cards должны искаться даже когда HERO сидит сверху;
- card OCR не должен подвешивать кадр GUI.
