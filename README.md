# synthesia-bridge

Convert sheet music images or PDFs into MIDI piano performances for use with Synthesia.

## Pipeline

```
Sheet Music (PNG/JPG/PDF)
    |
    v
[1] homr (Optical Music Recognition)
    |
    v
MusicXML
    |
    v
[2] music21 (MusicXML parser)
    |
    v
MIDI (.mid)
```

## Prerequisites

- Python 3.11 or higher
- CUDA-capable GPU (optional, speeds up OMR significantly)

## Installation

```bash
cd synthesia-bridge
pip install -e .

# For GPU support:
pip install -e ".[gpu]"
```

On first run, homr downloads ~500MB of ONNX model weights automatically.

## Usage

```bash
synthesia-bridge sheet_music.png
synthesia-bridge score.pdf
```

The resulting MIDI file is saved alongside the input file (e.g., `sheet_music.mid`).

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Limitations

homr's OMR currently focuses on pitch and rhythm for treble/bass clef. Dynamics, articulation, and double sharps/flats are not yet supported.

## License

AGPL-3.0 (inherited from homr).
