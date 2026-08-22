import cv2
from poker.vision.pokerdom.config import ROIS
from poker.vision.pokerdom.table_detector import TableDetector
from poker.vision.pokerdom.cards import CardRecognizer
from poker.vision.pokerdom.players import PlayerRecognizer
from poker.vision.pokerdom.tracker import HandTracker

class PokerDomExtractor:
    def __init__(self, tesseract_cmd=None):
        self.detector = TableDetector()
        self.cards = CardRecognizer()
        self.players = PlayerRecognizer()
        self.tracker = HandTracker()

        if tesseract_cmd:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def extract(self, image_path):
        """
        Main entry point for the frame processing.
        Returns a JSON-serializable dictionary matching the requested format.
        """
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Cannot read {image_path}")

        # 1. Find the table
        table_bbox = self.detector.find_table(img)
        if table_bbox is None:
            return None # Table not detected on this frame

        # 2. Extract Board and Hero Cards
        hero_roi = self.detector.get_absolute_roi(table_bbox, ROIS["hero_cards"])
        hx, hy, hw, hh = hero_roi
        hero_crop = img[hy:hy+hh, hx:hx+hw]
        hero_cards = self.cards.parse_cards(hero_crop)

        board_roi = self.detector.get_absolute_roi(table_bbox, ROIS["board"])
        bx, by, bw, bh = board_roi
        board_crop = img[by:by+bh, bx:bx+bw]
        board_cards = self.cards.parse_cards(board_crop)

        # Basic street logic based on board cards count
        if len(board_cards) == 0:
            street = "PREFLOP"
        elif len(board_cards) <= 3:
            street = "FLOP"
        elif len(board_cards) == 4:
            street = "TURN"
        else:
            street = "RIVER"

        # 3. Parse Players
        raw_players = []
        for seat_key, norm_roi in ROIS.items():
            if not seat_key.startswith("seat_"):
                continue

            px, py, pw, ph = self.detector.get_absolute_roi(table_bbox, norm_roi)
            seat_crop = img[py:py+ph, px:px+pw]

            p_data = self.players.parse_player_box(seat_key, seat_crop)
            raw_players.append(p_data)

        # 4. Track and merge across frames
        tracked_state = self.tracker.update_frame(raw_players)

        # 5. Format final JSON
        players_output = []
        for seat, state in tracked_state.items():
            players_output.append({
                "seat": seat,
                "name": state["name"],
                "action": state["last_action"],
                "stack": state["stack"]
            })

        return {
            "hero_cards": hero_cards,
            "board": board_cards,
            "street": street,
            "players": players_output
        }
