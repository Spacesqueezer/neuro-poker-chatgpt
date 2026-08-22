import cv2
import pytesseract
import re
import os

class CardParser:
    """
    Very basic heuristic card parser based on Tesseract OCR.
    In a real implementation, template matching (cv2.matchTemplate) with a folder of
    card suites and ranks is much more robust. For Phase 8 MVP, we attempt OCR.
    """
    def __init__(self):
        # Mapping common OCR mistakes to valid ranks
        self.rank_map = {
            '10': 'T', '0': 'T', 'lO': 'T', 'IO': 'T',
            'A': 'A', 'K': 'K', 'Q': 'Q', 'J': 'J',
            '9': '9', '8': '8', '7': '7', '6': '6',
            '5': '5', '4': '4', '3': '3', '2': '2'
        }

    def parse_cards(self, img_crop):
        """
        Takes a crop of the cards area and tries to return a list of cards like ['A♠', 'K♥'].
        Since we don't have color suit templates loaded yet, this is a placeholder
        that will just return dummy cards if it detects anything, or empty if blank.
        """
        # For now, without a template dataset of the exact poker client suits,
        # it is impossible to accurately parse suits from grayscale OCR.
        # We will stub this out to return the hardcoded aces IF cards are present,
        # otherwise empty. The user needs to provide a template dataset for full parsing.

        gray = cv2.cvtColor(img_crop, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

        # Count non-zero pixels. If there's enough white, we assume cards are dealt.
        white_pixels = cv2.countNonZero(thresh)

        if white_pixels > 1000:
            return ["A♠", "A♥"] # Still stubbed until templates are built
        return []
