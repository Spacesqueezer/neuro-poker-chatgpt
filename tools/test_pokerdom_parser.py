import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from poker.vision.pokerdom.extractor import PokerDomExtractor

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_pokerdom_parser.py <image_path>")
        sys.exit(1)

    extractor = PokerDomExtractor()
    result = extractor.extract(sys.argv[1])

    if result:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("Table not found or could not be parsed.")
