"""Explicit offline imitation training/evaluation for the new snapshot baseline."""

import json
import math
import time
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader

from poker.learning.advisor_contract import ACTIONS
from poker.learning.snapshot_actions import decode
from poker.learning.snapshot_dataset import digest, load_dataset
from poker.learning.snapshot_encoding import layout_for, layout_hash
from poker.learning.snapshot_metrics import PolicyMetrics, action_report, evaluation_text
from poker.learning.snapshot_model import SnapshotPolicy, batch_tensors, checkpoint, load_checkpoint
from poker.learning.snapshot_symmetry import permute_encoded

OBJECTIVES = ("legacy-v1", "balanced-bb-v2")
AUGMENTATIONS = ("none", "suit-permutation-v1")


def collate(rows, *, suit_generator=None):
    encoded = [row["encoded"] for row in rows]
    if suit_generator is not None:
        encoded = [
            permute_encoded(item, torch.randperm(4, generator=suit_generator).tolist())
            for item in encoded
        ]
    lows, spans = [], []
    for row in rows:
        observation = row["observation"]
        if row["sizing_mask"]:
            action = ACTIONS[row["action_index"]]
            low, high = (observation.legal[action + "_to_" + b] for b in ("min", "max"))
            lows.append(low / observation.big_blind)
            spans.append((high - low) / observation.big_blind)
        else:
            lows.append(0.0)
            spans.append(0.0)
    return {
        **batch_tensors(encoded),
        "action_index": torch.tensor([r["action_index"] for r in rows], dtype=torch.long),
        "sizing_target": torch.tensor([r["sizing_fraction"] for r in rows], dtype=torch.float32),
        "sizing_mask": torch.tensor([r["sizing_mask"] for r in rows], dtype=torch.bool),
        "sizing_min_bb": torch.tensor(lows, dtype=torch.float32),
        "sizing_span_bb": torch.tensor(spans, dtype=torch.float32),
    }


def train_class_weights(rows):
    """Inverse-square-root frequency, normalized to mean weight 1 on train only."""
    counts = Counter(row["action_index"] for row in rows)
    if not counts:
        raise ValueError("Empty training split")
    weights = [1 / math.sqrt(counts[i]) if counts[i] else 0.0 for i in range(len(ACTIONS))]
    mean = sum(counts[i] * weights[i] for i in range(len(ACTIONS))) / len(rows)
    return torch.tensor([v / mean if v else 1.0 for v in weights], dtype=torch.float32)


def training_loaders(data, *, batch_size, seed, augmentation="none"):
    if augmentation not in AUGMENTATIONS:
        raise ValueError("Unknown training augmentation")
    # A separate generator leaves initialization and batch order unchanged.
    suit_generator = (
        torch.Generator().manual_seed(seed ^ 0x5A17)
        if augmentation == "suit-permutation-v1"
        else None
    )
    return {
        name: DataLoader(
            data[name],
            batch_size=batch_size,
            shuffle=name == "train",
            collate_fn=partial(collate, suit_generator=suit_generator)
            if name == "train"
            else collate,
            generator=torch.Generator().manual_seed(seed) if name == "train" else None,
        )
        for name in ("train", "validation")
    }


def loss_terms(outputs, batch, *, objective="legacy-v1", class_weights=None):
    if objective not in OBJECTIVES:
        raise ValueError("Unknown training objective")
    action_errors = nn.functional.cross_entropy(
        outputs["action_logits"], batch["action_index"], reduction="none"
    )
    if objective == "balanced-bb-v2":
        if class_weights is None:
            raise ValueError("Train-only class weights required")
        action_errors = action_errors * class_weights[batch["action_index"]]
        mask = batch["sizing_mask"] & (batch["sizing_span_bb"] > 0)
        predicted = batch["sizing_min_bb"] + outputs["sizing_fraction"] * batch["sizing_span_bb"]
        expected = batch["sizing_min_bb"] + batch["sizing_target"] * batch["sizing_span_bb"]
        error = nn.functional.smooth_l1_loss(predicted.log1p(), expected.log1p(), reduction="none")
        sizing = (error * mask).sum() / mask.sum().clamp_min(1)
    else:
        error = nn.functional.smooth_l1_loss(
            outputs["sizing_fraction"], batch["sizing_target"], reduction="none"
        )
        sizing = (error * batch["sizing_mask"]).mean()
    action = action_errors.mean()
    loss = action + sizing
    if not torch.isfinite(loss):
        raise ValueError("Nonfinite training loss")
    return loss, action, sizing


def epoch(model, loader, device, optimizer=None, *, objective="legacy-v1", class_weights=None):
    model.train(optimizer is not None)
    totals = Counter()
    confusion = torch.zeros(len(ACTIONS), len(ACTIONS), dtype=torch.long)
    started = time.perf_counter()
    with torch.set_grad_enabled(optimizer is not None):
        for cpu_batch in loader:
            batch = {k: v.to(device) for k, v in cpu_batch.items()}
            outputs = model(
                **{k: batch[k] for k in ("table", "players", "seat_mask", "action_mask")}
            )
            loss, action_loss, sizing_loss = loss_terms(
                outputs, batch, objective=objective, class_weights=class_weights
            )
            if optimizer is not None:
                optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 5.0, error_if_nonfinite=True)
                optimizer.step()
            count = len(batch["action_index"])
            totals["samples"] += count
            totals["action_loss"] += action_loss.item() * count
            size_count = (
                count
                if objective == "legacy-v1"
                else int((batch["sizing_mask"] & (batch["sizing_span_bb"] > 0)).sum().item())
            )
            totals["sizing_denominator"] += size_count
            totals["sizing_loss"] += sizing_loss.item() * size_count
            predicted = outputs["action_logits"].argmax(1)
            totals["correct"] += (predicted == batch["action_index"]).sum().item()
            totals["batches"] += 1
            confusion += torch.bincount(
                (batch["action_index"] * len(ACTIONS) + predicted).cpu(),
                minlength=len(ACTIONS) ** 2,
            ).reshape(len(ACTIONS), len(ACTIONS))
    action_loss = totals["action_loss"] / totals["samples"]
    sizing_loss = totals["sizing_loss"] / max(1, totals["sizing_denominator"])
    return {
        "samples": totals["samples"],
        "loss": action_loss + sizing_loss,
        "action_loss": action_loss,
        "sizing_loss": sizing_loss,
        "correct": totals["correct"] / totals["samples"],
        "sizing_denominator": totals["sizing_denominator"],
        "batches": totals["batches"],
        "elapsed_seconds": time.perf_counter() - started,
        **action_report(confusion.tolist()),
    }


def empty_output(path):
    path = Path(path)
    if path.exists() and any(path.iterdir()):
        raise ValueError("Choose an empty output directory; existing runs are preserved")
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def preflight(directory, *, feature_set="raw-v1"):
    data, manifest = load_dataset(directory, feature_set=feature_set)
    return {
        "samples": {name: len(rows) for name, rows in data.items()},
        "dataset": manifest["config"],
        "teacher": manifest["teacher"],
        "feature_set": feature_set,
        "input_encoding": layout_for(feature_set)["encoding"],
        "input_layout_sha256": layout_hash(feature_set),
        "table_feature_count": len(layout_for(feature_set)["table_features"]),
        "training_run": False,
        "policy_called": False,
    }


def train(
    directory,
    output,
    *,
    epochs=20,
    batch_size=128,
    seed=42,
    learning_rate=0.001,
    device="cpu",
    objective="legacy-v1",
    augmentation="none",
    feature_set="raw-v1",
    progress=None,
):
    if epochs < 1 or batch_size < 1 or not math.isfinite(learning_rate) or learning_rate <= 0:
        raise ValueError("Positive epochs, batch size and finite learning rate required")
    if objective not in OBJECTIVES:
        raise ValueError("Unknown training objective")
    if augmentation not in AUGMENTATIONS:
        raise ValueError("Unknown training augmentation")
    data, manifest = load_dataset(directory, feature_set=feature_set)
    output = empty_output(output)
    torch.manual_seed(seed)
    model = SnapshotPolicy(feature_set=feature_set).to(device)
    class_weights = (
        train_class_weights(data["train"]).to(device) if objective == "balanced-bb-v2" else None
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    loaders = training_loaders(data, batch_size=batch_size, seed=seed, augmentation=augmentation)
    config = {
        "epochs": epochs,
        "batch_size": batch_size,
        "seed": seed,
        "learning_rate": learning_rate,
        "device": device,
        "objective": objective,
        "augmentation": augmentation,
        "feature_set": feature_set,
        "suit_augmentation_seed": seed ^ 0x5A17 if augmentation != "none" else None,
    }
    run = {
        "schema_version": "snapshot-training-run/1",
        "status": "running",
        "config": config,
        "dataset_manifest_sha256": digest(Path(directory) / "manifest.json"),
        "dataset_splits_sha256": manifest["split_sha256"],
        "teacher": manifest["teacher"],
        "source_sha256": {p.name: digest(p) for p in Path(__file__).parent.glob("snapshot_*.py")},
        "torch_version": str(torch.__version__),
        "model_config": model.config,
        "input_layout": layout_for(feature_set),
        "input_layout_sha256": layout_hash(feature_set),
        "history": [],
        "training_run": True,
        "test_used_for_selection": False,
        "class_weights_train_only": class_weights.cpu().tolist()
        if class_weights is not None
        else None,
        "class_counts_train": dict(Counter(ACTIONS[r["action_index"]] for r in data["train"])),
        "started_at": datetime.now(UTC).isoformat(),
        "training_steps": 0,
    }
    write_json(output / "run.json", run)
    best = float("inf")
    started = time.perf_counter()
    for number in range(1, epochs + 1):
        training = epoch(
            model,
            loaders["train"],
            device,
            optimizer,
            objective=objective,
            class_weights=class_weights,
        )
        validation = epoch(
            model, loaders["validation"], device, objective=objective, class_weights=class_weights
        )
        metrics = {"epoch": number, "train": training, "validation": validation}
        run["history"].append(metrics)
        run["training_steps"] += training["batches"]
        run["elapsed_seconds"] = time.perf_counter() - started
        if validation["loss"] < best:
            best = validation["loss"]
            torch.save(checkpoint(model), output / "best.pt")
            run["best_epoch"] = number
        write_json(output / "run.json", run)
        if progress:
            progress(metrics)
    run.update(
        status="complete",
        checkpoint_sha256=digest(output / "best.pt"),
        finished_at=datetime.now(UTC).isoformat(),
    )
    write_json(output / "run.json", run)
    return run


def evaluate(directory, model_path, output, *, device="cpu"):
    model = load_checkpoint(model_path, device=device)
    data, manifest = load_dataset(directory, feature_set=model.feature_set)
    output = empty_output(output)
    counts = Counter()
    confusion = [[0] * len(ACTIONS) for _ in ACTIONS]
    frequency = Counter(r["action_index"] for r in data["train"])
    diagnostics = PolicyMetrics()
    variant_counts: dict[str, Counter[str]] = {}
    variant_metrics: dict[str, PolicyMetrics] = {}
    with (output / "predictions.jsonl").open("w", encoding="utf-8") as log, torch.no_grad():
        for row in data["test"]:
            outputs = model(**batch_tensors([row["encoded"]], device=device))
            predicted = int(outputs["action_logits"].argmax(1).item())
            fraction = float(outputs["sizing_fraction"].item())
            decision = decode(row["observation"], predicted, fraction)
            expected = row["action_index"]
            counts["samples"] += 1
            counts["correct_actions"] += predicted == expected
            baseline = max(
                (i for i, m in enumerate(row["encoded"].action_mask) if m),
                key=lambda i: frequency[i],
            )
            counts["baseline_correct"] += baseline == expected
            if row["sizing_mask"]:
                counts["sizing_targets"] += 1
                counts["sizing_absolute_error"] += abs(fraction - row["sizing_fraction"])
            confusion[expected][predicted] += 1
            sizing_detail = diagnostics.add(row, predicted, fraction)
            variant = getattr(row["observation"], "hand_variant", "standard")
            if variant not in variant_counts:
                variant_counts[variant] = Counter()
                variant_metrics[variant] = PolicyMetrics()
            group = variant_counts[variant]
            group["samples"] += 1
            group["correct_actions"] += predicted == expected
            group["baseline_correct"] += baseline == expected
            variant_metrics[variant].add(row, predicted, fraction)
            log.write(
                json.dumps(
                    {
                        "prediction": asdict(decision),
                        "target_action": ACTIONS[expected],
                        "sizing_fraction": fraction,
                        "sizing_diagnostic": sizing_detail,
                    }
                )
                + "\n"
            )
    result = {
        "schema_version": "snapshot-evaluation/1",
        "split": "test",
        "counts": dict(counts),
        "action_agreement": counts["correct_actions"] / counts["samples"],
        "legal_majority_baseline_agreement": counts["baseline_correct"] / counts["samples"],
        "sizing_fraction_mae": counts["sizing_absolute_error"] / counts["sizing_targets"]
        if counts["sizing_targets"]
        else None,
        "action_order": list(ACTIONS),
        "confusion_true_rows_predicted_columns": confusion,
        "checkpoint_sha256": digest(Path(model_path)),
        "input_encoding": layout_for(model.feature_set)["encoding"],
        "input_layout_sha256": layout_hash(model.feature_set),
        "dataset_test_sha256": manifest["split_sha256"]["test"],
        "teacher": manifest["teacher"],
        "measures_poker_profitability": False,
        "training_run": False,
        "hud_connected": False,
        "diagnostics": diagnostics.report(),
        "variants": {
            name: {
                "counts": dict(group),
                "action_agreement": group["correct_actions"] / group["samples"],
                "diagnostics": variant_metrics[name].report(),
            }
            for name, group in variant_counts.items()
        },
    }
    write_json(output / "evaluation.json", result)
    (output / "review.md").write_text(evaluation_text(result), encoding="utf-8")
    return result
