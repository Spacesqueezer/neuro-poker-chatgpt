# Vision — Hybrid Nickname OCR v6

This changes the runtime nickname recognition architecture.

Previous architecture:

```text
name ROI -> Tesseract -> identity tracker
```

New architecture:

```text
name ROI
  -> Tesseract proposes candidate text / length
  -> segment_known_name()
  -> CharacterTemplatePredictor checks every character
  -> high-confidence template corrections
  -> combined OCR/template score
  -> identity tracker
```

Why:

The PokerDom font is fixed. Tesseract is a general-purpose OCR engine and can
confidently confuse visually similar characters even on clean enlarged ROIs.
The project already has a labeled `a-z`, `0-9`, `_` template database, so that
database should participate in runtime recognition.

Important safeguards:

- templates do NOT blindly overwrite Tesseract;
- replacement requires both a good template score and a margin over the
  second-best character;
- Tesseract is still used to propose candidate string length, which makes
  segmentation much more reliable than fully blind character splitting;
- multiple preprocessing variants compete using a combined score;
- `*****` remains a dedicated hidden-name state;
- dash is removed: valid runtime/template alphabet is `a-z`, `0-9`, `_`.

Files changed:

- `src/poker/vision/ocr/name_reader.py`
- `src/poker/vision/recognition/name_template_predictor.py`
