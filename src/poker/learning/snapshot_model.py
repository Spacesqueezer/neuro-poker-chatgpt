"""Versioned shared-seat policies for raw and explicit-card snapshot features."""

import torch
from torch import nn

from poker.learning.advisor_contract import ACTIONS
from poker.learning.snapshot_encoding import (
    MAX_PLAYERS,
    PLAYER_FEATURES,
    feature_set_of,
    layout_for,
    layout_hash,
)

CHECKPOINT = "snapshot-policy-checkpoint/1"
CHECKPOINT_V2 = "snapshot-policy-checkpoint/2"
CHECKPOINT_V3 = "snapshot-policy-checkpoint/3"
CHECKPOINT_FEATURES = {
    CHECKPOINT: "raw-v1",
    CHECKPOINT_V2: "cards-v2",
    CHECKPOINT_V3: "variants-v3",
}


class SnapshotPolicy(nn.Module):
    def __init__(self, seat_width=32, hidden_width=128, *, feature_set="raw-v1"):
        super().__init__()
        self.feature_set = feature_set
        self.table_width = len(layout_for(feature_set)["table_features"])
        if type(seat_width) is not int or type(hidden_width) is not int:
            raise ValueError("Network widths must be integers")
        if not 1 <= seat_width <= 1024 or not 1 <= hidden_width <= 4096:
            raise ValueError("Unsupported network widths")
        self.config = {"seat_width": seat_width, "hidden_width": hidden_width}
        if feature_set != "raw-v1":
            self.config["feature_set"] = feature_set
        self.seat_encoder = nn.Sequential(
            nn.Linear(len(PLAYER_FEATURES), seat_width),
            nn.ReLU(),
            nn.Linear(seat_width, seat_width),
            nn.ReLU(),
        )
        self.trunk = nn.Sequential(
            nn.Linear(self.table_width + 2 * seat_width, hidden_width),
            nn.ReLU(),
            nn.Linear(hidden_width, hidden_width),
            nn.ReLU(),
        )
        self.action_head = nn.Linear(hidden_width, len(ACTIONS))
        self.sizing_head = nn.Linear(hidden_width, 1)

    def forward(self, table, players, seat_mask, action_mask):
        count = table.shape[0] if table.ndim == 2 else -1
        if (
            table.shape != (count, self.table_width)
            or players.shape != (count, MAX_PLAYERS, len(PLAYER_FEATURES))
            or seat_mask.shape != (count, MAX_PLAYERS)
            or action_mask.shape != (count, len(ACTIONS))
            or count <= 0
        ):
            raise ValueError("Invalid snapshot batch shapes")
        for value in (table, players, seat_mask, action_mask):
            if not torch.isfinite(value).all():
                raise ValueError("Nonfinite model input")
        for mask in (seat_mask, action_mask):
            if not ((mask == 0) | (mask == 1)).all():
                raise ValueError("Masks must contain zero or one")
        if (
            not (seat_mask[:, 0] == 1).all()
            or not (seat_mask.sum(dim=1) >= 2).all()
            or not (action_mask.sum(dim=1) >= 1).all()
        ):
            raise ValueError("Missing hero, table or available actions")
        # Padding cannot affect the pool, even if a caller supplies nonzero padding.
        seats = self.seat_encoder(players)
        pooled = (seats * seat_mask.unsqueeze(-1)).sum(dim=1) / seat_mask.sum(dim=1, keepdim=True)
        state = self.trunk(torch.cat((table, seats[:, 0], pooled), dim=1))
        logits = self.action_head(state).masked_fill(action_mask == 0, float("-inf"))
        return {
            "action_logits": logits,
            "sizing_fraction": torch.sigmoid(self.sizing_head(state)).squeeze(-1),
        }


def batch_tensors(encoded, *, device="cpu"):
    if not encoded or len({feature_set_of(r) for r in encoded}) != 1:
        raise ValueError("Empty or incompatible encoded batch")
    return {
        key: torch.tensor([getattr(r, key) for r in encoded], dtype=torch.float32, device=device)
        for key in ("table", "players", "seat_mask", "action_mask")
    }


def checkpoint(model):
    return {
        "schema_version": next(k for k, v in CHECKPOINT_FEATURES.items() if v == model.feature_set),
        "encoding": layout_for(model.feature_set)["encoding"],
        "layout_sha256": layout_hash(model.feature_set),
        "config": dict(model.config),
        "state_dict": model.state_dict(),
    }


def load_checkpoint(path, *, device="cpu"):
    data = torch.load(path, map_location=device, weights_only=True)
    if not isinstance(data, dict) or (
        data.get("schema_version") not in CHECKPOINT_FEATURES
        or set(data) != {"schema_version", "encoding", "layout_sha256", "config", "state_dict"}
    ):
        raise ValueError("Incompatible checkpoint; legacy 330-feature weights are not supported")
    feature_set = CHECKPOINT_FEATURES[data["schema_version"]]
    fields = {"seat_width", "hidden_width"}
    if feature_set != "raw-v1":
        fields.add("feature_set")
    if not isinstance(data["config"], dict) or set(data["config"]) != fields:
        raise ValueError("Invalid model configuration")
    if (
        data.get("encoding") != layout_for(feature_set)["encoding"]
        or data.get("layout_sha256") != layout_hash(feature_set)
        or data["config"].get("feature_set", "raw-v1") != feature_set
    ):
        raise ValueError("Incompatible checkpoint feature layout")
    model = SnapshotPolicy(**data["config"])
    model.load_state_dict(data["state_dict"], strict=True)
    model.to(device)
    model.eval()
    return model
