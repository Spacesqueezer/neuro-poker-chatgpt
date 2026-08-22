import cv2
import numpy as np
import os

class CardRecognizer:
    def __init__(self, templates_dir="templates/cards"):
        self.templates_dir = templates_dir
        self.rank_templates = {}
        self.suit_templates = {'red': {}, 'black': {}}
        self._load_templates()

    def _load_templates(self):
        """Loads rank and suit templates if they exist in the templates directory."""
        if not os.path.exists(self.templates_dir):
            return

        ranks_dir = os.path.join(self.templates_dir, "ranks")
        suits_dir = os.path.join(self.templates_dir, "suits")

        # Load ranks
        if os.path.exists(ranks_dir):
            for file in os.listdir(ranks_dir):
                if file.endswith(".png"):
                    rank = file.split('.')[0]
                    img = cv2.imread(os.path.join(ranks_dir, file), cv2.IMREAD_GRAYSCALE)
                    if img is not None:
                        self.rank_templates[rank] = img

        # Load suits
        if os.path.exists(suits_dir):
            for file in os.listdir(suits_dir):
                if file.endswith(".png"):
                    suit = file.split('.')[0]
                    img = cv2.imread(os.path.join(suits_dir, file), cv2.IMREAD_GRAYSCALE)
                    if img is not None:
                        if suit in ['hearts', 'diamonds', 'h', 'd']:
                            self.suit_templates['red'][suit[0].lower()] = img
                        elif suit in ['clubs', 'spades', 'c', 's']:
                            self.suit_templates['black'][suit[0].lower()] = img

    def _find_card_rectangles(self, image):
        """Finds white rectangles in the given ROI image."""
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        # White cards generally have low saturation and high value
        lower_white = np.array([0, 0, 180])
        upper_white = np.array([180, 50, 255])
        mask = cv2.inRange(hsv, lower_white, upper_white)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        cards = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = w * h
            # Filter by area and aspect ratio of a typical card
            if area > 500 and 0.4 < w/h < 0.9:
                cards.append((x, y, w, h))

        # Sort left to right
        cards.sort(key=lambda b: b[0])
        return cards

    def _match_template(self, roi_gray, templates, threshold=0.8):
        """Matches a grayscale ROI against a dictionary of templates."""
        best_match = None
        best_val = threshold

        for name, template in templates.items():
            if roi_gray.shape[0] < template.shape[0] or roi_gray.shape[1] < template.shape[1]:
                continue # Template is larger than the ROI

            res = cv2.matchTemplate(roi_gray, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)

            if max_val > best_val:
                best_val = max_val
                best_match = name

        return best_match

    def _is_red(self, card_bgr):
        """Heuristic to check if the card's suit is red based on center pixels."""
        # Check center region for dominant red color
        h, w = card_bgr.shape[:2]
        center = card_bgr[h//4:3*h//4, w//4:3*h//4]

        # Calculate average color
        avg_color_per_row = np.average(center, axis=0)
        avg_color = np.average(avg_color_per_row, axis=0)
        b, g, r = avg_color

        # If red channel is significantly higher than blue and green
        return r > b + 20 and r > g + 20

    def parse_cards(self, image):
        """Returns a list of parsed cards (e.g., ['Ah', 'Kd'])."""
        card_rects = self._find_card_rectangles(image)
        parsed_cards = []

        for x, y, w, h in card_rects:
            card_img = image[y:y+h, x:x+w]
            card_gray = cv2.cvtColor(card_img, cv2.COLOR_BGR2GRAY)

            # The rank and suit are usually in the top-left corner
            # These ratios might need adjustment based on specific card design
            top_left_roi = card_gray[0:int(h*0.4), 0:int(w*0.4)]

            rank = self._match_template(top_left_roi, self.rank_templates)

            # Determine color for suit matching
            is_red = self._is_red(card_img)
            suit_templates_to_use = self.suit_templates['red'] if is_red else self.suit_templates['black']

            suit = self._match_template(top_left_roi, suit_templates_to_use)

            # Fallback if templates are missing (prevents total failure during development)
            if not rank or not suit:
                # If we detected a card blob but don't have templates, return unknown
                parsed_cards.append("??")
            else:
                parsed_cards.append(f"{rank}{suit}")

        return parsed_cards
