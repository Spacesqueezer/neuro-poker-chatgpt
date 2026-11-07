"""Keep train/validation bytes fixed and replace a diagnosed test with fresh hands."""

import json
import shutil
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from contextlib import ExitStack
from pathlib import Path

from poker.learning.snapshot_dataset import (
    SPLITS,
    digest,
    generate_hand,
    load_dataset,
    source_hashes,
)


def assigned_seeds(manifest):
    if "assigned_seeds" in manifest:
        return {seed for seeds in manifest["assigned_seeds"].values() for seed in seeds}
    config = manifest["config"]
    return set(
        range(config["seed"], config["seed"] + config["hands"] + config.get("extra_train_hands", 0))
    )


def prepare_holdout(
    source, output, *, hands=1000, seed=201000, workers=5, exclude=(), progress=None
):
    if (
        any(type(v) is not int for v in (hands, seed, workers))
        or hands < 30
        or not 1 <= workers <= 32
    ):
        raise ValueError("Need at least 30 hands, integer seed and 1..32 workers")
    source, output = Path(source), Path(output)
    data, parent = load_dataset(source)
    if "assigned_seeds" not in parent:
        raise ValueError("Source must declare full seed assignments")
    manifests = {str(source.resolve()): digest(source / "manifest.json")}
    used = assigned_seeds(parent)
    for directory in map(Path, exclude):
        _, manifest = load_dataset(directory)
        used.update(assigned_seeds(manifest))
        manifests[str(directory.resolve())] = digest(directory / "manifest.json")
    seeds = list(range(seed, seed + hands))
    if used.intersection(seeds):
        raise ValueError("Fresh holdout seeds overlap a previous dataset")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Choose an empty output directory")
    output.mkdir(parents=True, exist_ok=True)
    sources = source_hashes()
    for name in ("train", "validation"):
        shutil.copyfile(source / f"{name}.jsonl", output / f"{name}.jsonl")
    labels, streets, rejections = Counter(), Counter(), Counter()
    count, observed = 0, set()
    samples = parent["config"]["equity_samples"]
    jobs = [(n, samples, False) for n in seeds]
    with ExitStack() as opened:
        log = opened.enter_context((output / "test.jsonl").open("w", encoding="utf-8"))
        if workers == 1:
            results = map(generate_hand, jobs)
        else:
            pool = opened.enter_context(ProcessPoolExecutor(max_workers=workers))
            results = pool.map(generate_hand, jobs, chunksize=4)
        for i, (rows, rejected) in enumerate(results, 1):
            rejections.update(rejected)
            for row in rows:
                log.write(json.dumps(row, ensure_ascii=False) + "\n")
                count += 1
                observed.add(row["deal_seed"])
                labels["test:" + row["target"]["action"]] += 1
                streets["test:" + row["observation"]["street"]] += 1
            if progress and i % 100 == 0:
                progress(i, count)
    if source_hashes() != sources:
        raise ValueError("Source files changed during generation; dataset left incomplete")
    for name in ("train", "validation"):
        if digest(output / f"{name}.jsonl") != parent["split_sha256"][name]:
            raise ValueError("Copied training/validation split changed")
    manifest = {
        "schema_version": parent["schema_version"],
        "layout_sha256": parent["layout_sha256"],
        "generator_version": "snapshot-holdout-replacement/1",
        "config": {"hands": hands, "seed": seed, "equity_samples": samples, "workers": workers},
        "teacher": parent["teacher"],
        "split_method": "unchanged_parent_train_validation_new_natural_test",
        "assigned_seeds": {**parent["assigned_seeds"], "test": seeds},
        "samples": {**parent["samples"], "test": count},
        "hands_with_samples": {**parent["hands_with_samples"], "test": len(observed)},
        "labels": {
            **{k: v for k, v in parent["labels"].items() if not k.startswith("test:")},
            **labels,
        },
        "streets": {
            **{k: v for k, v in parent["streets"].items() if not k.startswith("test:")},
            **streets,
        },
        "rejections_new_test": dict(rejections),
        "split_sha256": {name: digest(output / f"{name}.jsonl") for name in SPLITS},
        "source_sha256_new_test": sources,
        "copied_splits": {
            "parent": str(source.resolve()),
            "manifest_sha256": digest(source / "manifest.json"),
            "splits": ["train", "validation"],
        },
        "excluded_datasets": manifests,
        "training_run": False,
        "player_db_written": False,
    }
    # Keep provenance valid if a source manifest is replaced while workers run.
    if any(
        digest(Path(path) / "manifest.json") != expected for path, expected in manifests.items()
    ):
        raise ValueError("Source manifest changed during generation")
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    load_dataset(output)
    return manifest
