"""Offline fixed-state diagnostics; no training and no hidden opponent cards."""

import json
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
from functools import lru_cache
from itertools import permutations
from pathlib import Path

from poker.agents.expert import ExpertAgent
from poker.learning.advisor_contract import ACTIONS
from poker.learning.snapshot_dataset import digest, generate_hand, load_dataset, source_hashes
from poker.learning.snapshot_encoding import encode
from poker.learning.snapshot_symmetry import permute_encoded
from poker.strategy.ranges import PositionRangeModel


class CachedRanges(PositionRangeModel):
    """Identical ordered distribution and RNG draws, cached for one fixed state."""

    def __init__(self):
        super().__init__()
        self.cached = lru_cache(maxsize=16)(super().combo_distribution)

    def combo_distribution(self, available, player, state):
        return self.cached(tuple(available), player, state)


class FixedEquity:
    def __init__(self, value):
        self.value = value

    def estimate(self, state):
        return self.value


def recheck(state, legal, *, samples, seeds):
    """Estimate independently, then reuse the existing teacher's exact decision rules."""
    result = []
    ranges = CachedRanges()
    for seed in seeds:
        agent = ExpertAgent(seed=seed, equity_samples=samples, range_model=ranges)
        equity = agent.equity.estimate(state)
        agent.equity = FixedEquity(equity)
        decision = agent.choose_action(state, legal)
        if not legal.allows(decision.action, decision.amount):
            raise ValueError("Rechecked teacher returned an illegal action")
        result.append(
            {
                "seed": seed,
                "equity": equity,
                "action": decision.action.value,
                "amount_to": decision.amount if decision.action.value in ("bet", "raise") else None,
            }
        )
    return result


def replay_cases(job):
    (
        seed,
        original_samples,
        predictions,
        equity_samples,
        repeats,
        original_equity_samples,
        *scenarios,
    ) = job
    wanted = set(predictions)
    captured = {}

    def capture(state, legal, decision, sample):
        observation_id = sample["observation"]["observation_id"]
        if observation_id in wanted:
            captured[observation_id] = (state, legal, sample)

    scenario = scenarios[0] if scenarios else "standard-v1"
    generated_job: tuple[int, int, bool] | tuple[int, int, bool, str] = (
        seed,
        original_equity_samples,
        False,
    )
    if scenario != "standard-v1":
        generated_job = (*generated_job, scenario)
    regenerated, _ = generate_hand(generated_job, decision_observer=capture)
    if regenerated != original_samples or set(captured) != wanted:
        raise ValueError(f"Original trajectory/records did not reproduce for seed {seed}")
    result = []
    for observation_id, (state, legal, sample) in captured.items():
        seeds = [seed * 37 + int(observation_id) * 1009 + i * 104729 for i in range(repeats)]
        full = recheck(state, legal, samples=equity_samples, seeds=seeds)
        no_history = recheck(
            replace(state, action_history=()), legal, samples=equity_samples, seeds=seeds
        )
        result.append(
            {
                "deal_seed": seed,
                "observation_id": observation_id,
                "sample": sample,
                "prediction": predictions[observation_id],
                "public_state": asdict(state),
                "legal": {**asdict(legal), "actions": [a.value for a in legal.actions]},
                "with_history": full,
                "without_history": no_history,
                "original_trajectory_exact": True,
            }
        )
    return result


def suit_audit(rows, checkpoint_path):
    import torch

    from poker.learning.snapshot_model import batch_tensors, load_checkpoint

    model = load_checkpoint(checkpoint_path)
    orders = list(permutations(range(4)))
    details = []
    with torch.no_grad():
        for row in rows:
            encoded = encode(row["observation"], feature_set=model.feature_set)
            batch = [permute_encoded(encoded, order) for order in orders]
            outputs = model(**batch_tensors(batch))
            probabilities = outputs["action_logits"].softmax(1)
            choices = outputs["action_logits"].argmax(1).tolist()
            expected = row["action_index"]
            details.append(
                {
                    "hand_id": row["observation"].hand_id,
                    "observation_id": row["observation"].observation_id,
                    "target": ACTIONS[expected],
                    "original_prediction": ACTIONS[choices[0]],
                    "votes": dict(Counter(ACTIONS[i] for i in choices)),
                    "averaged_prediction": ACTIONS[int(probabilities.mean(0).argmax())],
                    "probability_range": {
                        a: [float(probabilities[:, i].min()), float(probabilities[:, i].max())]
                        for i, a in enumerate(ACTIONS)
                    },
                }
            )
    return details


def audit(
    directory,
    checkpoint_path,
    evaluation_directory,
    output,
    *,
    samples=512,
    repeats=3,
    workers=5,
    progress=print,
):
    if samples < 1 or repeats < 1 or not 1 <= workers <= 32:
        raise ValueError("Positive sample/repeat counts and 1..32 workers required")
    directory, checkpoint_path = Path(directory), Path(checkpoint_path)
    evaluation_directory, output = Path(evaluation_directory), Path(output)
    from poker.learning.snapshot_model import load_checkpoint

    model = load_checkpoint(checkpoint_path)
    data, manifest = load_dataset(directory, feature_set=model.feature_set)
    evaluation = json.loads((evaluation_directory / "evaluation.json").read_text(encoding="utf-8"))
    if (
        evaluation["checkpoint_sha256"] != digest(checkpoint_path)
        or evaluation["dataset_test_sha256"] != manifest["split_sha256"]["test"]
    ):
        raise ValueError("Evaluation does not belong to these weights and test records")
    predictions_path = evaluation_directory / "predictions.jsonl"
    predictions = [
        json.loads(line) for line in predictions_path.read_text(encoding="utf-8").splitlines()
    ]
    records = [
        json.loads(line)
        for line in (directory / "test.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    if len(predictions) != len(records):
        raise ValueError("Incomplete prediction log")
    groups, selected = {}, {}
    for record, prediction in zip(records, predictions, strict=True):
        obs, pred = record["observation"], prediction["prediction"]
        if (obs["hand_id"], obs["observation_id"], record["target"]["action"]) != (
            pred["hand_id"],
            pred["observation_id"],
            prediction["target_action"],
        ):
            raise ValueError("Mismatched prediction identity or label")
        seed = record["deal_seed"]
        groups.setdefault(seed, []).append(record)
        truth = record["target"]["action"]
        if (pred["action"] == "raise" and truth != "raise") or (
            truth == "bet" and pred["action"] != "bet"
        ):
            selected.setdefault(seed, {})[obs["observation_id"]] = pred
    if output.exists() and any(output.iterdir()):
        raise ValueError("Choose an empty audit output directory")
    output.mkdir(parents=True, exist_ok=True)
    sources = source_hashes()
    suits = suit_audit(data["test"], checkpoint_path)
    if any(
        row["original_prediction"] != pred["prediction"]["action"]
        for row, pred in zip(suits, predictions, strict=True)
    ):
        raise ValueError("Stored predictions do not reproduce with these weights")
    (output / "suits.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in suits), encoding="utf-8"
    )
    if progress:
        progress(
            f"Suit audit: {sum(len(row['votes']) > 1 for row in suits)}"
            f"/{len(suits)} changed actions",
            flush=True,
        )
    jobs = [
        (
            seed,
            groups[seed],
            preds,
            samples,
            repeats,
            manifest["config"]["equity_samples"],
            manifest["config"].get("scenario", "standard-v1"),
        )
        for seed, preds in selected.items()
    ]
    cases = []
    with (
        ProcessPoolExecutor(max_workers=workers) as pool,
        (output / "cases.jsonl").open("w", encoding="utf-8") as log,
    ):
        for batch in pool.map(replay_cases, jobs):
            for row in batch:
                cases.append(row)
                log.write(json.dumps(row, ensure_ascii=False) + "\n")
            log.flush()
            if progress:
                progress(
                    f"Rechecked {len(cases)}/{sum(map(len, selected.values()))} fixed states",
                    flush=True,
                )
    if source_hashes() != sources:
        raise ValueError("Source files changed during audit")
    report = {
        "schema_version": "snapshot-fixed-state-audit/1",
        "cases": len(cases),
        "hands": len(jobs),
        "samples_per_repeat": samples,
        "independent_repeats": repeats,
        "sources_sha256": sources,
        "checkpoint_sha256": digest(checkpoint_path),
        "test_sha256": manifest["split_sha256"]["test"],
        "predictions_sha256": digest(predictions_path),
        "suit_changed_actions": sum(len(row["votes"]) > 1 for row in suits),
        "suit_average_correct": sum(row["averaged_prediction"] == row["target"] for row in suits),
        "original_correct": sum(row["original_prediction"] == row["target"] for row in suits),
        "test_used_for_diagnosis": True,
        "training_run": False,
        "hud_connected": False,
        "interpretation": (
            "Teacher rechecks remain heuristic; history ablation changes available "
            "information, not real observed history."
        ),
    }
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
