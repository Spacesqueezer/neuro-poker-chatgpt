import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from poker.vision.state_extractor import GameStateExtractor
from poker.vision.translator import ScreenTranslator

extractor = GameStateExtractor()
state = extractor.extract_state("/tmp/sample.png")
print("Extracted state:", state)

# Dummy test just to make sure things import and parse
assert state['pot'] == 5.67
assert state['hero']['stack'] == 200.0

print("All tests passed.")
