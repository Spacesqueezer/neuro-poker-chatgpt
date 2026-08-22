"""
Normalized ROIs for PokerDom.
Values are (x_norm, y_norm, w_norm, h_norm) relative to the detected table bounding box.
"""

# Normalized against the main green table contour
ROIS = {
    "board": (0.25, 0.35, 0.50, 0.20),
    "hero_cards": (0.40, 0.75, 0.20, 0.15),
    "hero_info": (0.40, 0.90, 0.20, 0.10),

    # Example seat positions (to be adjusted based on actual PokerDom layout)
    "seat_1_bottom_left": (0.10, 0.70, 0.15, 0.10),
    "seat_2_left": (0.05, 0.40, 0.15, 0.10),
    "seat_3_top_left": (0.15, 0.10, 0.15, 0.10),
    "seat_4_top_right": (0.70, 0.10, 0.15, 0.10),
    "seat_5_right": (0.80, 0.40, 0.15, 0.10),
    "seat_6_bottom_right": (0.75, 0.70, 0.15, 0.10),
}
