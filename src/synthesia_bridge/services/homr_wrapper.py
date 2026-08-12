from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree

import pymupdf as fitz


def pdf_page_to_image(page: fitz.Page) -> bytes:
    """Render one PDF page as PNG bytes."""
    pixmap = page.get_pixmap(dpi=300, alpha=False)
    return pixmap.tobytes("png")


def pdf_page_to_musicxml(page: fitz.Page) -> ElementTree.ElementTree:
    """Run HOMR on one PDF page and return its MusicXML document."""
    with tempfile.TemporaryDirectory() as temporary_directory:
        image_path = Path(temporary_directory) / "page.png"
        musicxml_path = image_path.with_suffix(".musicxml")
        image_path.write_bytes(pdf_page_to_image(page))

        subprocess.run(
            [sys.executable, "-m", "homr.main", str(image_path)],
            check=True,
        )

        if not musicxml_path.is_file():
            raise FileNotFoundError(f"HOMR did not create {musicxml_path.name}")

        return ElementTree.parse(musicxml_path)


def download_musicXML(
    element_tree: ElementTree.ElementTree,
    output_path: str | Path = "output.musicxml",
) -> Path:
    """Write MusicXML to the current directory or a requested output path."""
    output = Path(output_path)
    element_tree.write(output, encoding="unicode", xml_declaration=True)
    return output


def main() -> int:
    pdf_path = Path("moonlight.pdf")  # Set this to the PDF you want to process.

    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")

    with fitz.open(pdf_path) as document:
        if len(document) == 0:
            raise ValueError(f"PDF does not contain any pages: {pdf_path}")
        musicxml = pdf_page_to_musicxml(document[0])

    output = download_musicXML(musicxml)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
