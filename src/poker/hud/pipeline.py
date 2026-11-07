"""One immutable frame feeds names, cards, game phase and draw probabilities."""

import time
from dataclasses import dataclass

import cv2
import numpy as np

from poker.hud.cards import find_cards
from poker.hud.hand import HandObservation, observe
from poker.hud.odds import estimate
from poker.hud.recognition import analyze, layout_panels


def my_turn(frame):
    h, w = frame.shape[:2]
    buttons = frame[round(h * 0.90) :, round(w * 0.25) : round(w * 0.74)]
    hsv = cv2.cvtColor(buttons, cv2.COLOR_BGR2HSV)
    green = cv2.inRange(hsv, (38, 120, 100), (85, 255, 255))
    yellow = cv2.inRange(hsv, (12, 150, 110), (37, 255, 255))
    red = cv2.inRange(hsv, (0, 120, 110), (10, 255, 255))
    red |= cv2.inRange(hsv, (165, 120, 110), (179, 255, 255))
    return all(float(np.mean(mask > 0)) > 0.035 for mask in (green, yellow, red))


@dataclass
class FrameAnalysis:
    players: list
    hand: HandObservation
    elapsed_ms: float = 0.0


def analyze_frame(frame, include_players=True, hero_seat=6):
    started = time.monotonic()
    players = analyze(frame) if include_players else []
    cards = find_cards(frame) if hero_seat == 6 else find_cards(frame, hero_seat=hero_seat)
    hand = observe(cards, my_turn(frame), bool(layout_panels(frame)))
    if hand.valid:
        hand.odds = estimate(hand.hero, hand.board)
    return FrameAnalysis(players, hand, round((time.monotonic() - started) * 1000, 1))
