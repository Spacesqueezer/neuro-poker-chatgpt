"""Compare saved button amounts with an independent wager-field reading, offline."""

import argparse
import hashlib
import json
from pathlib import Path

import cv2

from poker.hud import slider
from poker.hud.client_id import read_hand_id
from poker.hud.recognition import configure_ocr
from poker.hud.slider import EndpointConfirmation, field_and_knob
from poker.hud.slider import rail_geometry as rail_geometry
from poker.hud.slider import read_field as read_field
from poker.hud.slider import read_field_view as read_field_view
from poker.hud.slider import remove_field_caret as remove_field_caret


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("observations", type=Path)
    args = parser.parse_args()
    configure_ocr()
    tracker = EndpointConfirmation()
    output = args.observations.with_name("slider_evidence.jsonl")
    review = [
        "# Независимая проверка поля ставки",
        "",
        "Координата ползунка не подтверждает допустимые границы. Модель не вызывается.",
        "",
    ]
    counts = {"active_frames": 0, "amount_agreements": 0, "amount_conflicts": 0, "unknown_field": 0}
    with output.open("w", encoding="utf8") as stream:
        for line in args.observations.read_text(encoding="utf8").splitlines():
            row = json.loads(line)
            if not row["controls"]["flags"]:
                tracker.previous = None
                continue
            frame = cv2.imread(row["image"])
            if frame is None:
                raise ValueError(f"Cannot read {row['image']}")
            evidence = field_and_knob(frame)
            identity = read_hand_id(frame)
            confirmation = tracker.update(row, identity, evidence)
            for key, found in (
                ("confirmed_endpoints", confirmation is not None),
                ("left_frames", evidence["endpoint"] == "left"),
                ("right_frames", evidence["endpoint"] == "right"),
                ("interior_frames", evidence["endpoint"] == "interior"),
            ):
                counts[key] = counts.get(key, 0) + int(found)
            selected = row["controls"].get("selected_wager")
            value = (evidence["field"] or {}).get("value")
            agreement = selected["value"] == value if selected and value is not None else None
            counts["active_frames"] += 1
            counts["amount_agreements"] += agreement is True
            counts["amount_conflicts"] += agreement is False
            counts["unknown_field"] += value is None
            status = (
                "совпадает"
                if agreement is True
                else "конфликт"
                if agreement is False
                else "не подтверждено"
            )
            review.append(
                f"- Кадр {row['frame_id']}: поле {value}; кнопка "
                f"{selected['value'] if selected else None}; {status}; положение "
                f"{evidence['endpoint']}; подтверждено двумя кадрами: {confirmation is not None}."
            )
            stream.write(
                json.dumps(
                    {
                        "frame_id": row["frame_id"],
                        "captured_at": row["captured_at"],
                        "image": row["image"],
                        "selected_wager": selected,
                        "amount_agreement": agreement,
                        "hand_identity": identity,
                        "confirmed_endpoint": confirmation,
                        **evidence,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    print(json.dumps(counts))
    args.observations.with_name("slider_summary.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                **counts,
                "model_called": False,
                "input_sha256": hashlib.sha256(args.observations.read_bytes()).hexdigest(),
                "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "slider_source_sha256": hashlib.sha256(
                    Path(slider.__file__).read_bytes()
                ).hexdigest(),
            },
            indent=2,
        ),
        encoding="utf8",
    )
    args.observations.with_name("slider_review.md").write_text(
        "\n".join(review) + "\n", encoding="utf8"
    )
    print(output.resolve())


if __name__ == "__main__":
    main()
