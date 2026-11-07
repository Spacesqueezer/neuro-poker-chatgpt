"""Place HUD cards near seats without covering name ROIs or previous cards."""


def overlap(a, b):
    x, y, w, h = a
    bx, by, bw, bh = b
    return max(0, min(x + w, bx + bw) - max(x, bx)) * max(0, min(y + h, by + bh) - max(y, by))


def place_card(roi, size, card_size, obstacles):
    x, y, w, h = roi
    width, height = size
    cw, ch = card_size
    preferred = [
        (x + (w - cw) // 2, y - ch - 6),
        (x + (w - cw) // 2, y + h + 6),
        (x - cw - 6, y),
        (x + w + 6, y),
    ]
    candidates = preferred + [
        (cx, cy)
        for cy in range(6, max(7, height - ch), 24)
        for cx in range(6, max(7, width - cw), 32)
    ]
    candidates = [
        (min(max(0, cx), max(0, width - cw)), min(max(0, cy), max(0, height - ch)), cw, ch)
        for cx, cy in candidates
    ]

    def score(box):
        collision = sum(overlap(box, obstacle) for obstacle in obstacles)
        distance = abs(box[0] + cw / 2 - (x + w / 2)) + abs(box[1] + ch / 2 - (y + h / 2))
        return collision * 10000 + distance

    return min(candidates, key=score)
