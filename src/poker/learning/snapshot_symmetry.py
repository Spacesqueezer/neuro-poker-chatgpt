"""Poker-preserving symmetries of the versioned numerical snapshot input."""

from dataclasses import replace

from poker.learning.snapshot_encoding import TABLE_FEATURES, feature_set_of


def permute_encoded(encoded, suit_order):
    """One global bijection of suits, preserving ranks and all other features."""
    feature_set_of(encoded)
    if sorted(suit_order) != list(range(4)):
        raise ValueError("Expected a permutation of four suits")
    table = list(encoded.table)
    for offset in (TABLE_FEATURES.index("hero.2c"), TABLE_FEATURES.index("board.2c")):
        for rank in range(13):
            for suit, new_suit in enumerate(suit_order):
                table[offset + rank * 4 + new_suit] = encoded.table[offset + rank * 4 + suit]
    return replace(encoded, table=tuple(table))
