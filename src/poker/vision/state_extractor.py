import cv2
import pytesseract
import re
import os
import sys

from poker.vision.roi_config import HERO_NAME, HERO_STACK, MAIN_POT, BOARD_CARDS, OPPONENT_BOXES

class GameStateExtractor:
    def __init__(self, tesseract_cmd=None):
        self.tessdata_dir = None
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        elif sys.platform == "win32":
            # Auto-configure tesseract for standard Windows installation paths
            standard_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                r"D:\Program Files\Tesseract-OCR\tesseract.exe"
            ]

            import shutil
            found_path = shutil.which("tesseract")
            if found_path:
                standard_paths.insert(0, found_path)

            # Check for tesseract.exe
            for path in standard_paths:
                if os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    tessdata_path = os.path.join(os.path.dirname(path), "tessdata")
                    if os.path.exists(tessdata_path):
                        self.tessdata_dir = tessdata_path
                        # Force overwrite the environment variable, in case the user has it set incorrectly
                        os.environ["TESSDATA_PREFIX"] = tessdata_path
                    break

    def _crop(self, image, box):
        x, y, w, h = box
        return image[y:y+h, x:x+w]

    def _ocr_text(self, image, config="--psm 7"):
        if self.tessdata_dir:
            config += f' --tessdata-dir "{self.tessdata_dir}"'
        return pytesseract.image_to_string(image, config=config).strip()

    def _clean_number(self, text):
        # Remove any non-numeric characters except comma or period
        cleaned = re.sub(r'[^\d,\.]', '', text)
        # Convert comma to dot
        cleaned = cleaned.replace(',', '.')
        try:
            return float(cleaned)
        except ValueError:
            return None

    def extract_state(self, image_path):
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not read image at {image_path}")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Some elements are white on black, invert for better OCR in some cases
        _, thresh_inv = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)

        state = {
            "hero": {},
            "pot": 0.0,
            "board": [],
            "opponents": {}
        }

        # Hero Name
        hero_name_img = self._crop(gray, HERO_NAME)
        state["hero"]["name"] = self._ocr_text(hero_name_img)

        # Hero Stack
        hero_stack_img = self._crop(thresh_inv, HERO_STACK)
        stack_text = self._ocr_text(hero_stack_img)
        state["hero"]["stack"] = self._clean_number(stack_text)

        # Pot
        pot_img = self._crop(thresh_inv, MAIN_POT)
        pot_text = self._ocr_text(pot_img)
        # E.g., "5aHK: 5,67 p."
        match = re.search(r'(\d+[\.,]\d+)', pot_text)
        if match:
            state["pot"] = self._clean_number(match.group(1))
        else:
            matches = re.findall(r'([\d,\.]+)', pot_text)
            if matches:
                state["pot"] = self._clean_number(matches[-1])

        # Opponents
        for opp_name, box in OPPONENT_BOXES.items():
            opp_img = self._crop(thresh_inv, box)
            # Use PSM 6 for block of text
            opp_text = self._ocr_text(opp_img, config="--psm 6")

            # Simple heuristic: look for numbers followed by 'p.' or just lines with numbers
            stack_match = re.search(r'([\d,\.]+)\s*[pP\.]', opp_text)
            if stack_match:
                stack_val = self._clean_number(stack_match.group(1))
                state["opponents"][opp_name] = {"stack": stack_val, "raw_text": opp_text.replace('\n', ' ')}
            else:
                # Fallback, just store raw text if any
                if opp_text:
                    state["opponents"][opp_name] = {"stack": None, "raw_text": opp_text.replace('\n', ' ')}

        return state

if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python state_extractor.py <image_path>")
        sys.exit(1)

    extractor = GameStateExtractor()
    state = extractor.extract_state(sys.argv[1])
    print(json.dumps(state, indent=2, ensure_ascii=False))
