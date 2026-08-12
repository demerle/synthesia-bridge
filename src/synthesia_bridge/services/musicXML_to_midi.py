from pathlib import Path
from xml.etree import ElementTree

import pymupdf as fitz
from music21 import converter, stream

from synthesia_bridge.services.homr_wrapper import pdf_page_to_musicxml


def musicXML_to_midi(music_xml: ElementTree.ElementTree) -> stream.Score:
    """Convert an in-memory MusicXML document into a music21 score."""
    xml_data = ElementTree.tostring(music_xml.getroot(), encoding="unicode")
    return converter.parseData(xml_data, format="musicxml")


def download_midi(
    midi: stream.Score,
    output_path: str | Path = "output.mid",
) -> Path:
    """Write a music21 score as a MIDI file and return its path."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    midi.write("midi", fp=str(output))
    return output


def main() -> int:
    pdf_path = Path("moonlight.pdf")  # Set this to the PDF you want to convert.

    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")

    with fitz.open(pdf_path) as document:
        if len(document) == 0:
            raise ValueError(f"PDF does not contain any pages: {pdf_path}")
        musicxml = pdf_page_to_musicxml(document[0])

    midi = musicXML_to_midi(musicxml)
    output = download_midi(midi)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
