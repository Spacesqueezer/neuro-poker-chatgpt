"""Synchronous offline advice with a strict pre-inference gate and input binding.

No capture, HUD integration, click execution, network access or database writes.
Matching an observation hash does not certify live capture freshness.
"""

# Existing snapshot codecs/model helpers are validated at runtime, not yet typed.
# mypy: disable-error-code="no-untyped-call"

import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from poker.learning.snapshot_contract import SnapshotRejected, from_dict
from poker.learning.snapshot_dataset import digest
from poker.learning.snapshot_encoding import encode, layout_for
from poker.learning.snapshot_sizing import SIZING_POLICIES, sized_decision

ADVICE_VERSION = "snapshot-offline-advice/1"


def observation_json(payload: Any) -> str:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")
    )


def observation_hash(payload: Any) -> str:
    return hashlib.sha256(observation_json(payload).encode("utf-8")).hexdigest()


def matches_observation(advice: dict[str, Any], payload: Any) -> bool:
    """Bind to the exact current input; the caller must separately establish its freshness."""
    try:
        observation = from_dict(payload)
        decision = advice.get("decision")
        return (
            advice.get("schema_version") == ADVICE_VERSION
            and advice.get("status") == "ready"
            and advice.get("observation_sha256") == observation_hash(payload)
            and advice.get("hand_id") == observation.hand_id
            and advice.get("observation_id") == observation.observation_id
            and isinstance(decision, dict)
            and decision.get("hand_id") == observation.hand_id
            and decision.get("observation_id") == observation.observation_id
        )
    except (ValueError, TypeError, AttributeError):
        return False


class SnapshotAdvisor:
    def __init__(self, checkpoint_path: str | Path, *, sizing_policy: str, device: str = "cpu"):
        if sizing_policy not in SIZING_POLICIES:
            raise ValueError("Choose an explicit supported sizing policy")
        from poker.learning.snapshot_model import load_checkpoint

        path = Path(checkpoint_path)
        before = digest(path)
        self.model = load_checkpoint(path, device=device)
        if digest(path) != before:
            raise ValueError("Checkpoint changed while loading")
        self.checkpoint_sha256 = before
        self.sizing_policy = sizing_policy
        self.device = device

    def advise(self, payload: Any) -> dict[str, Any]:
        import torch

        from poker.learning.snapshot_model import batch_tensors

        started = time.perf_counter()
        result: dict[str, Any] = {
            "schema_version": ADVICE_VERSION,
            "status": "blocked",
            "hand_id": None,
            "observation_id": None,
            "observation_sha256": None,
            "checkpoint_sha256": self.checkpoint_sha256,
            "input_encoding": layout_for(self.model.feature_set)["encoding"],
            "sizing_policy": self.sizing_policy,
            "model_called": False,
            "blockers": [],
            "decision": None,
            "sizing_trace": None,
            "neural_diagnostic": None,
            "offline_only": True,
        }
        try:
            # Freeze a JSON copy before validating or running the model.
            wire = json.loads(observation_json(payload))
            result["observation_sha256"] = observation_hash(wire)
            if isinstance(wire, dict):
                for key in ("hand_id", "observation_id"):
                    if isinstance(wire.get(key), str):
                        result[key] = wire[key]
            observation = from_dict(wire)
            if any(type(getattr(observation, k)) is not str for k in ("hand_id", "observation_id")):
                raise ValueError("Identity must be a string")
            encoded = encode(observation, feature_set=self.model.feature_set)
        except SnapshotRejected as error:
            result["blockers"] = list(error.reasons)
        except (ValueError, TypeError):
            result["blockers"] = ["malformed_snapshot"]
        else:
            result["model_called"] = True
            with torch.inference_mode():
                batch = batch_tensors([encoded], device=self.device)
                outputs = self.model(**batch)
            logits, fraction = outputs["action_logits"], outputs["sizing_fraction"]
            available = batch["action_mask"].bool()
            if (
                logits.shape != (1, 6)
                or fraction.shape != (1,)
                or not torch.isfinite(logits[available]).all()
                or not torch.isneginf(logits[~available]).all()
                or not torch.isfinite(fraction).all()
                or not ((fraction >= 0) & (fraction <= 1)).all()
            ):
                result["blockers"] = ["model_output_invalid"]
            else:
                index, value = int(logits.argmax(1).item()), float(fraction.item())
                neural, _ = sized_decision(
                    observation, index, policy="neural-range-v1", neural_fraction=value
                )
                decision, trace = sized_decision(
                    observation, index, policy=self.sizing_policy, neural_fraction=value
                )
                result.update(
                    status="ready",
                    decision=asdict(decision),
                    sizing_trace=trace,
                    neural_diagnostic={"decision": asdict(neural), "sizing_fraction": value},
                )
        result["elapsed_ms"] = (time.perf_counter() - started) * 1000
        return result
