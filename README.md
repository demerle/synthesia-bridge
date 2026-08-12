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

HOMR currently focuses on pitch and rhythm for treble and bass clef. Dynamics,
articulation, and double sharps/flats are not fully supported.

## License

AGPL-3.0 (inherited from HOMR).
