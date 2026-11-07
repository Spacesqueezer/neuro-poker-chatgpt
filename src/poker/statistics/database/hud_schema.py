"""SQLAlchemy metadata for the HUD observation ledger (migration 0006)."""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table, Text, false


def register_hud_tables(metadata):
    Table(
        "hud_aliases",
        metadata,
        Column("alias_key", String(256), primary_key=True),
        Column("player_key", String(256), ForeignKey("hud_players.player_key"), nullable=False),
        Column("evidence", Text, nullable=False),
        Column("corrected_at", String(40), nullable=False),
    )
    Table(
        "hud_players",
        metadata,
        Column("player_key", String(256), primary_key=True),
        Column("room", String(32), nullable=False),
        Column("display_name", String(128), nullable=False),
        Column("note", Text, nullable=False, server_default=""),
        Column("first_seen", String(40), nullable=False),
        Column("last_seen", String(40), nullable=False),
    )
    Table(
        "hud_hands",
        metadata,
        Column("hand_key", String(256), primary_key=True),
        Column("client_id", String(32), nullable=False),
        Column("table_key", String(128), nullable=False),
        Column("observed_at", String(40), nullable=False),
        Column("hero_seen", Boolean, nullable=False, server_default=false()),
        Column("confirmed", Boolean, nullable=False, server_default=false()),
    )
    sightings = Table(
        "hud_sightings",
        metadata,
        Column("hand_key", String(256), ForeignKey("hud_hands.hand_key"), primary_key=True),
        Column("source", String(128), primary_key=True),
        Column("seat", Integer, primary_key=True),
        Column("player_key", String(256), ForeignKey("hud_players.player_key")),
        Column("raw_name", Text, nullable=False),
        Column("evidence", Text, nullable=False),
    )
    actions = Table(
        "hud_actions",
        metadata,
        Column("event_id", String(128), primary_key=True),
        Column("hand_key", String(256), ForeignKey("hud_hands.hand_key"), nullable=False),
        Column("player_key", String(256), ForeignKey("hud_players.player_key"), nullable=False),
        Column("action", String(16), nullable=False),
        Column("source", String(32), nullable=False),
        Column("evidence", Text, nullable=False),
    )
    from sqlalchemy import Index

    Index("ix_hud_sightings_player", sightings.c.player_key, sightings.c.hand_key)
    Index("ix_hud_actions_player", actions.c.player_key)
