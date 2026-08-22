import cv2
import pytesseract
import re
import os

class PlayerRecognizer:
    def __init__(self, templates_dir="templates/actions"):
        self.templates_dir = templates_dir
        self.action_templates = {}
        self._load_templates()

    def _load_templates(self):
        """Loads action button templates (CHECK, FOLD, etc)."""
        if not os.path.exists(self.templates_dir):
            return

        for file in os.listdir(self.templates_dir):
            if file.endswith(".png"):
                action = file.split('.')[0].upper()
                img = cv2.imread(os.path.join(self.templates_dir, file), cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    self.action_templates[action] = img

    def _match_action(self, image_gray, threshold=0.85):
        """Attempts to match the player's info box against action templates."""
        if not self.action_templates:
            return None

        best_match = None
        best_val = threshold

        for action_name, template in self.action_templates.items():
            if image_gray.shape[0] < template.shape[0] or image_gray.shape[1] < template.shape[1]:
                continue

            res = cv2.matchTemplate(image_gray, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)

            if max_val > best_val:
                best_val = max_val
                best_match = action_name

        return best_match

    def _ocr_text(self, image, config="--psm 7"):
        return pytesseract.image_to_string(image, config=config).strip()

    def _clean_number(self, text):
        cleaned = re.sub(r'[^\d,\.]', '', text)
        cleaned = cleaned.replace(',', '.')
        try:
            return float(cleaned)
        except ValueError:
            return None

    def parse_player_box(self, seat_name, image):
        """
        Parses a single player's seat box.
        Returns a dict with action, name, and stack.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 1. Try to detect an action (FOLD, CHECK, etc.) first.
        action = self._match_action(gray)

        if action:
            # If an action is displayed, the client usually hides the name/stack
            return {
                "seat": seat_name,
                "action": action,
                "name": None,
                "stack": None
            }

        # 2. If no action, fallback to OCR for name and stack.
        # Assuming typical layout: Top half is name, bottom half is stack.
        h, w = gray.shape
        top_half = gray[0:h//2, 0:w]
        bottom_half = gray[h//2:h, 0:w]

        # Invert for better OCR if it's white text on dark background
        _, top_inv = cv2.threshold(top_half, 150, 255, cv2.THRESH_BINARY_INV)
        _, bot_inv = cv2.threshold(bottom_half, 150, 255, cv2.THRESH_BINARY_INV)

        name = self._ocr_text(top_inv)
        stack_text = self._ocr_text(bot_inv, config="--psm 7")

        # Attempt to parse stack number
        stack = self._clean_number(stack_text)

        return {
            "seat": seat_name,
            "action": None, # Active player, no action displayed currently
            "name": name if name else None,
            "stack": stack
        }
