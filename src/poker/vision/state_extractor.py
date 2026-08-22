import cv2
import pytesseract
import re
import os
import sys

from poker.vision.roi_config import HERO_NAME, HERO_STACK, HERO_CARDS, MAIN_POT, BOARD_CARDS, OPPONENT_BOXES
from poker.vision.card_parser import CardParser

class GameStateExtractor:
    def __init__(self, tesseract_cmd=None):
        self.tessdata_dir = None
        self.card_parser = CardParser()
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

    def is_table_present(self, img_gray):
        # Quick heuristic to determine if poker table is actually on screen
        # We can check if we can read the Hero name or Pot text
        hero_name_img = self._crop(img_gray, HERO_NAME)
        name_text = self._ocr_text(hero_name_img)
        if len(name_text) > 3:
            return True
        return False

    def draw_debug_rois(self, img):
        debug_img = img.copy()
        color = (0, 255, 0)
        thickness = 2

        # Hero
        hx, hy, hw, hh = HERO_NAME
        cv2.rectangle(debug_img, (hx, hy), (hx+hw, hy+hh), color, thickness)
        hx, hy, hw, hh = HERO_STACK
        cv2.rectangle(debug_img, (hx, hy), (hx+hw, hy+hh), color, thickness)
        hx, hy, hw, hh = HERO_CARDS
        cv2.rectangle(debug_img, (hx, hy), (hx+hw, hy+hh), (255, 0, 0), thickness)

        # Pot and Board
        px, py, pw, ph = MAIN_POT
        cv2.rectangle(debug_img, (px, py), (px+pw, py+ph), color, thickness)
        bx, by, bw, bh = BOARD_CARDS
        cv2.rectangle(debug_img, (bx, by), (bx+bw, by+bh), (0, 0, 255), thickness)

        # Opponents
        for name, box in OPPONENT_BOXES.items():
            ox, oy, ow, oh = box
            cv2.rectangle(debug_img, (ox, oy), (ox+ow, oy+oh), color, thickness)

        return debug_img

    def extract_state(self, image_path):
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not read image at {image_path}")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        if not self.is_table_present(gray):
            return None # Skip parsing if table is not detected

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

        # Cards
        hero_cards_img = self._crop(img, HERO_CARDS)
        state["hero"]["cards"] = self.card_parser.parse_cards(hero_cards_img)

        board_cards_img = self._crop(img, BOARD_CARDS)
        state["board"] = self.card_parser.parse_cards(board_cards_img)

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
