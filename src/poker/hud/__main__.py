import argparse
import json
from datetime import datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Новый прозрачный Neuro HUD")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument(
        "--database", type=Path, help="SQLite со статистикой реальных игроков; только чтение"
    )
    parser.add_argument(
        "--replay", type=Path, help="Папка снимков: распознать table.png без запуска HUD"
    )
    parser.add_argument("--stats-file", type=Path, help="Рабочая SQLite для записи статистики HUD")
    args = parser.parse_args()
    if args.replay:
        import cv2

        from poker.hud.pipeline import analyze_frame
        from poker.hud.recognition import annotate, configure_ocr

        configure_ocr()
        output = args.root / "artifacts/hud" / f"replay_{datetime.now():%Y%m%d_%H%M%S}"
        output.mkdir(parents=True, exist_ok=True)
        report = []
        for path in sorted(args.replay.glob("*/table.png")):
            frame = cv2.imread(str(path))
            if frame is None:
                raise OSError(f"Cannot read {path}")
            analysis = analyze_frame(frame)
            players = analysis.players
            report.append(
                {
                    "source": str(path),
                    "players": [p.to_dict() for p in players],
                    "hand": analysis.hand.to_dict(),
                }
            )
            cv2.imwrite(
                str(output / f"{path.parent.name}.png"),
                annotate(frame, players, analysis.hand.cards),
            )
            print(
                path.parent.name,
                "hero",
                analysis.hand.hero,
                "board",
                analysis.hand.board,
                "valid",
                analysis.hand.valid,
                "my_turn",
                analysis.hand.my_turn,
                flush=True,
            )
        (output / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Report: {output}")
    else:
        from poker.hud.app import HudApp

        HudApp(args.root, args.database, args.stats_file).run()


if __name__ == "__main__":
    main()
