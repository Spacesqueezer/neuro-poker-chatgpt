# Vision

Этап: поиск стола по трём якорям и определение ников игроков.

Что есть сейчас:
- стол ищется по трём якорям;
- внутри найденного стола рисуются ROI зон с никами;
- OCR читает ники игроков;
- в консоль выводятся ники игроков, а не служебные якоря;
- по F2 сохраняется полный стол и все вырезанные зоны ников.

Зависимости:

pip install pywin32 pytesseract

Также нужен установленный Tesseract OCR и доступный язык eng.

Запуск:

python src/poker/vision/runner.py

Управление:
- Q: выход
- F2: сохранить текущий стол и все зоны ников

Структура сохранений:

captures/
	table_0001.png
	table_0001_names/
		seat_top_left.png
		seat_top_center.png
		seat_right.png
		seat_bottom_right.png
		seat_bottom_center.png
		seat_bottom_left.png
