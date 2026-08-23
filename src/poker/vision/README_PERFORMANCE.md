# Vision performance cleanup

Изменения:
- сохранение кадров перенесено на F8;
- добавлен отдельный hotkey handler;
- добавлен FPS meter.

Причина:
OpenCV waitKey не подходит для нормальных горячих клавиш.

План:
capture loop отдельно от OCR.

Цели:
- capture: 30-60 FPS
- OCR names: 1-2 FPS
- actions/cards: 10-20 FPS
