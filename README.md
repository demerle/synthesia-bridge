# synthesia-bridge

Minimal Python wrapper for converting one PNG sheet-music image into MusicXML
with [HOMR](https://github.com/liebharc/homr).

## Installation

```bash
pip install -e .
```

For optional CUDA support:

```bash
pip install -e ".[gpu]"
```

HOMR downloads its model weights automatically on the first run.

## Usage

```bash
python scripts/homr_test.py sheet_music.png
```

The output is written next to the input image as `sheet_music.musicxml`.

Multi-page PDFs are supported: each page is run through HOMR separately and the
resulting MusicXML documents are merged into one score with continuous measure
numbers via `synthesia_bridge.services.homr_wrapper.pdf_to_musicxml`. The
existing MusicXML-to-MIDI conversion is unchanged.

HOMR currently focuses on pitch and rhythm for treble and bass clef. Dynamics,
articulation, and double sharps/flats are not fully supported.

### Tests

Run the fast unit tests:

```bash
python -m pytest tests/ -m "not e2e"
```

Run the full end-to-end test (real HOMR inference, ~1 minute):

```bash
python -m pytest tests/ -m e2e
```

## License

AGPL-3.0 (inherited from HOMR).

## License

AGPL-3.0 (inherited from HOMR).
