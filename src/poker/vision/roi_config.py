"""
Region of Interest (ROI) configuration for 1234x1059 resolution.
Coordinates are stored as (x, y, w, h).
"""

# Hero info
HERO_NAME = (520, 875, 160, 30)
HERO_STACK = (520, 900, 160, 30)
HERO_CARDS = (510, 720, 200, 150) # Rough bounding box for both pocket cards

# Main pot
MAIN_POT = (560, 410, 160, 30)

# Board cards (bounding box covering all 5 possible cards)
# Assuming typical layout based on discovered contour anchors
BOARD_CARDS = (400, 470, 350, 130)

# Opponent stacks / info boxes
# Rough estimates based on OCR + visual grid
OPPONENT_BOXES = {
    "opp_1_right_mid": (1000, 400, 200, 100),
    "opp_2_right_top": (800, 300, 200, 100),
    "opp_3_left_top": (200, 300, 200, 100),
    "opp_4_left_bot": (100, 650, 200, 100),
    "opp_5_right_bot": (1000, 650, 200, 100),
}
