"""Offline replay of raw snapshot-observation/1 JSONL into decisions/refusals."""

import argparse
import json
from collections import Counter
from pathlib import Path

from poker.learning.snapshot_advice import SnapshotAdvisor
from poker.learning.snapshot_dataset import digest
from poker.learning.snapshot_sizing import SIZING_POLICIES


def replay(input_path, output, checkpoint_path, *, sizing_policy, device="cpu"):
    input_path, output = Path(input_path), Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Choose an empty output directory")
    source_hash = digest(input_path)
    advisor = SnapshotAdvisor(checkpoint_path, sizing_policy=sizing_policy, device=device)
    output.mkdir(parents=True, exist_ok=True)
    counts, blockers = Counter(), Counter()
    with (
        input_path.open(encoding="utf-8") as source,
        (output / "advice.jsonl").open("w", encoding="utf-8") as log,
    ):
        for number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                payload = None
            result = advisor.advise(payload)
            result["source_line"] = number
            counts[result["status"]] += 1
            counts["model_calls"] += result["model_called"]
            blockers.update(result["blockers"])
            log.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n")
    if digest(input_path) != source_hash:
        raise ValueError("Input stream changed during replay")
    report = {
        "schema_version": "snapshot-advice-replay/1",
        "input_sha256": source_hash,
        "input_path": str(input_path.resolve()),
        "checkpoint_path": str(Path(checkpoint_path).resolve()),
        "checkpoint_sha256": advisor.checkpoint_sha256,
        "sizing_policy": sizing_policy,
        "counts": dict(counts),
        "blockers": dict(blockers),
        "training_run": False,
        "hud_connected": False,
        "player_db_written": False,
    }
    (output / "summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    text = [
        "# Офлайн-прогон советника",
        "",
        f"Режим размера: `{sizing_policy}`.",
        "",
        f"Готовых решений: {counts['ready']}; отказов: {counts['blocked']}; "
        f"вызовов модели: {counts['model_calls']}.",
        "",
        "| Причина отказа | Число |",
        "|---|---:|",
        *(f"| {key} | {count} |" for key, count in sorted(blockers.items())),
        "",
        "Правило expert-pot65-v1 воспроизводит размер эвристического учителя; "
        "это не результат обучения размера и не доказательство прибыльности.",
        "Журнал привязывает ответ к SHA256 входа. Возраст/свежесть живого кадра "
        "этот офлайн-инструмент не подтверждает. HUD, клики и БД не используются.",
        "",
    ]
    (output / "review.md").write_text("\n".join(text), encoding="utf-8")
    return report


def main():
    import torch

    torch.set_num_threads(1)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, required=True, help="Raw snapshot-observation/1 JSONL"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--sizing-policy", choices=SIZING_POLICIES, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    report = replay(
        args.input,
        args.output,
        args.checkpoint,
        sizing_policy=args.sizing_policy,
        device=args.device,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
