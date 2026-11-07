# OCR tests use local diagnostic frames when available; pure tests run everywhere.
# ruff: noqa: E402
from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")
pytest.importorskip("pytesseract")

from poker.hud.cards import find_cards
from poker.hud.pipeline import my_turn
from poker.hud.recognition import configure_ocr

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "number,hero,board",
    [
        (169, ("8s", "7s"), ("2s", "8c", "Qc", "6s")),
        (440, ("Qc", "7s"), ("9h", "Th", "2s")),
        (645, (), ("9d", "2d", "Qd")),
        (871, ("9h", "8s"), ()),
        (920, ("9h", "8s"), ("6s", "As", "9s")),
        (1609, ("Jh", "7h"), ("Ah", "2d", "9d")),
        (2009, (), ("Qs", "8s", "Jd", "6d", "2s")),
    ],
)
def test_comment_frames_not_used_as_rank_templates(number, hero, board):
    from poker.hud.hand import observe

    path = ROOT / f"artifacts/hud/sessions/session_20260910_202646_6464df/frames/{number:08}.jpg"
    if not path.exists():
        pytest.skip("Local diagnostic frame is not present")
    configure_ocr()
    cards = find_cards(cv2.imread(str(path)))
    assert tuple(c.value for c in cards if c.zone == "hero") == hero
    assert tuple(c.value for c in cards if c.zone == "board") == board
    assert all(c.confidence >= 75 for c in cards)
    hand = observe(cards)
    assert hand.valid == bool(hero)
    if hand.valid:
        from poker.hud.odds import estimate

        assert estimate(hand.hero, hand.board)["runouts"] > 0
    else:
        assert hand.odds is None


@pytest.mark.parametrize(
    "frame,board",
    [
        (1378, ("9d", "7h", "Td")),
        (1442, ("9d", "7h", "Td", "7c")),
        (1584, ("7d", "As", "9c")),
        (2540, ("Qh", "Ts", "Th")),
    ],
)
def test_latest_session_card_boundaries_and_ranks(frame, board):
    path = ROOT / f"artifacts/hud/sessions/session_20260910_092618_a572b1/frames/{frame:08d}.jpg"
    if not path.exists():
        pytest.skip("Local diagnostic frame is not present")
    configure_ocr()
    cards = [c for c in find_cards(cv2.imread(str(path))) if c.zone == "board"]
    assert tuple(c.value for c in cards) == board
    assert all(c.confidence >= 75 for c in cards)


@pytest.mark.parametrize(
    "session,frame,board",
    [
        ("073154_ab5926", 398, ("2d", "4s", "9d")),
        ("074842_45e827", 299, ("Td", "4c", "2d")),
    ],
)
def test_session_nine_and_ten(session, frame, board):
    path = ROOT / f"artifacts/hud/sessions/session_20260910_{session}/frames/{frame:08d}.jpg"
    if not path.exists():
        pytest.skip("Local diagnostic frame is not present")
    configure_ocr()
    assert tuple(c.value for c in find_cards(cv2.imread(str(path))) if c.zone == "board") == board
    from poker.hud.client_id import read_hand_id

    identity = read_hand_id(cv2.imread(str(path)))
    assert identity["value"] == ("2861007497" if frame == 398 else "2861010122")
    assert identity["confidence"] >= 80


SAMPLES = [
    ("hud_20260909_083011_127917_238120", ("7s", "4h"), ("Ad", "8d", "5s"), False),
    ("hud_20260909_083114_816999_574191", ("5h", "4s"), ("Qd", "Jh", "Ac"), True),
    ("hud_20260909_083254_591770_425066", ("Tc", "3c"), (), False),
    ("hud_20260909_083301_744843_d99837", ("Tc", "3c"), (), True),
    ("hud_20260909_084813_314087_003bd0", ("Kd", "7d"), ("Qs", "6d", "3s"), True),
    ("hud_20260909_084848_813363_525e3e", ("Qh", "3d"), ("3s", "Js", "7s"), False),
]


def test_empty_frame_has_no_cards_or_turn_buttons():
    frame = np.zeros((600, 1000, 3), np.uint8)
    assert find_cards(frame) == [] and not my_turn(frame)


def test_new_frame_preserves_name_descenders_and_finds_dealer():
    from poker.hud.context import dealer_candidates
    from poker.hud.recognition import analyze

    path = ROOT / "captures/hud_20260909_225454_223431_66f9de/table.png"
    if not path.exists():
        pytest.skip("Local diagnostic capture is not present")
    configure_ocr()
    frame = cv2.imread(str(path))
    assert tuple(c.value for c in find_cards(frame) if c.zone == "board") == ("7c", "2h", "Td")
    assert any(p.name.casefold() == "xxx1yyy" for p in analyze(frame))
    dealers = dealer_candidates(frame)
    assert len(dealers) == 1
    x, y, w, h = dealers[0]["roi"]
    assert x <= 1140 < x + w and y <= 623 < y + h

    # Chips obscure this ten. Downsampling may remove enough detail that the
    # recognizer must abstain rather than invent a card and publish odds.
    from poker.hud.hand import observe

    hand = observe(find_cards(cv2.resize(frame, None, fx=0.5, fy=0.5)))
    assert hand.board[:2] == ("7c", "2h")
    assert hand.board[2] in ("", "Td")
    if not hand.board[2]:
        assert not hand.valid and hand.odds is None


@pytest.mark.parametrize("sample,hero,board,turn", SAMPLES)
@pytest.mark.parametrize("scale", [1, 0.5])
def test_local_frames_match_visually_checked_cards(sample, hero, board, turn, scale):
    path = ROOT / "captures" / sample / "table.png"
    if not path.exists():
        pytest.skip("Local HUD diagnostic capture is not present")
    try:
        configure_ocr()
    except Exception as error:
        pytest.skip(f"Tesseract not installed: {error}")
    frame = cv2.imread(str(path))
    frame = cv2.resize(frame, None, fx=scale, fy=scale)
    result = find_cards(frame)
    assert tuple(c.value for c in result if c.zone == "hero") == hero
    assert tuple(c.value for c in result if c.zone == "board") == board
    assert my_turn(frame) == turn


@pytest.mark.parametrize("board_count", [4, 5])
def test_composed_turn_and_river_frames(board_count):
    from poker.hud.hand import observe

    paths = [ROOT / "captures" / SAMPLES[i][0] / "table.png" for i in (0, 2)]
    if not all(path.exists() for path in paths):
        pytest.skip("Local diagnostic frames are not present")
    configure_ocr()
    frame, source = [cv2.imread(str(path)) for path in paths]
    # Add visually verified Tc/3c crops to the known Ad/8d/5s flop.
    for index in range(board_count - 3):
        card = source[955:1099, 1048 + 108 * index : 1150 + 108 * index]
        x = 1209 + index * 108
        frame[563:712, x : x + 102] = cv2.resize(card, (102, 149))
    hand = observe(find_cards(frame))
    assert hand.hero == ("7s", "4h")
    assert hand.board == ("Ad", "8d", "5s", "Tc", "3c")[:board_count]
    assert hand.valid
    assert hand.street == ("Тёрн" if board_count == 4 else "Ривер")


@pytest.mark.parametrize(
    "frame,board",
    [
        (642, ()),
        (652, ()),
        (976, ("Ah", "Td", "Ad")),
        (980, ("Ah", "Td", "Ad")),
        (1037, ("Ah", "Td", "Ad", "Ac")),
        (1059, ("Ah", "Td", "Ad", "Ac", "5d")),
    ],
)
def test_september23_small_cards(frame, board):
    path = ROOT / f"artifacts/hud/sessions/session_20260923_054209_82f838/requests/{frame:08d}.png"
    if not path.exists():
        pytest.skip("Local diagnostic frame is not present")
    configure_ocr()
    cards = find_cards(cv2.imread(str(path)))
    assert tuple(c.value for c in cards if c.zone == "board") == board
    assert tuple(c.value for c in cards if c.zone == "hero") == (
        ("9c", "7h") if frame < 900 else ("Ts", "6h")
    )
    assert all(c.confidence >= 75 for c in cards)


@pytest.mark.parametrize(
    "readings,expected",
    [
        ([("9", 81), ("9", 86)], "9"),
        ([("10", 84), ("10", 71)], "T"),
        ([("9", 90), ("8", 90)], ""),
        ([("9", 79), ("9", 79)], ""),
        ([("9", 95), ("9", 69)], ""),
        ([("g", 95)], ""),
    ],
)
def test_native_rank_agreement_guards(monkeypatch, readings, expected):
    from poker.hud import cards

    responses = iter(readings)

    def ocr(*args, **kwargs):
        text, confidence = next(responses, ("", 0))
        return {"text": [text], "conf": [confidence]}

    monkeypatch.setattr(cards.pytesseract, "image_to_data", ocr)
    result, _ = cards.native_rank_agreement(np.full((122, 84, 3), 255, np.uint8))
    assert result == expected
