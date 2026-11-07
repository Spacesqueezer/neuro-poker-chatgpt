"""Install the pinned Russian OCR data used for PokerDom button labels."""

import hashlib
import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/4.1.0/rus.traineddata"
SHA256 = "e16e5e036cce1d9ec2b00063cf8b54472625b9e14d893a169e2b0dedeb4df225"


def main():
    target = Path(__file__).resolve().parents[1] / "data/hud/tessdata/rus.traineddata"
    if target.exists():
        data = target.read_bytes()
    else:
        with urllib.request.urlopen(URL, timeout=60) as response:
            data = response.read()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError("OCR data checksum mismatch; existing file was not changed")
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(data)
    print(target)


if __name__ == "__main__":
    main()
