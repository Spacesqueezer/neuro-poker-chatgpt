import os
from pathlib import Path

import pytesseract


def configure_tesseract():
	candidates = [
		Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
		Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
	]

	tesseract_exe = next(
		(path for path in candidates if path.exists()),
		None,
	)

	if tesseract_exe is None:
		raise FileNotFoundError(
			"Tesseract executable not found in Program Files "
			"or Program Files (x86)."
		)

	tessdata = tesseract_exe.parent / "tessdata"

	if not tessdata.exists():
		raise FileNotFoundError(
			f"Tesseract tessdata directory not found: {tessdata}"
		)

	pytesseract.pytesseract.tesseract_cmd = str(
		tesseract_exe
	)

	# TESSDATA_PREFIX должен указывать именно на папку tessdata.
	os.environ["TESSDATA_PREFIX"] = str(
		tessdata
	)

	return {
		"executable": str(tesseract_exe),
		"tessdata": str(tessdata),
	}


TESSERACT_RUNTIME = configure_tesseract()
