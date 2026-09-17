from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree

import pymupdf as fitz

from synthesia_bridge.services.musicxml_cleanup import strip_unpaired_repeats


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


def _part_name(root: ElementTree.Element, part_id: str | None) -> str:
    """Look up a part's <part-name> via the page's <part-list>."""
    for score_part in root.findall("./part-list/score-part"):
        if score_part.get("id") == part_id:
            name = score_part.find("part-name")
            return name.text if name is not None and name.text is not None else ""
    return ""


def pdf_to_musicxml(document: fitz.Document) -> ElementTree.ElementTree:
    """Run HOMR on every page of a PDF, returning one combined MusicXML document.

    HOMR recognizes each page independently, so a page holding two systems of the
    same instrument (e.g. two piano grand staves) is emitted as two <part>
    elements. Parts are matched across pages by instrument name and merged: every
    measure of a given instrument appends into a single <part> with continuous
    measure numbers across the whole score. A page introducing an instrument
    absent from page 1 raises ValueError.
    """
    if len(document) == 0:
        raise ValueError("PDF does not contain any pages")

    page_trees = [pdf_page_to_musicxml(page) for page in document]

    base_root = page_trees[0].getroot()
    base_parts = list(base_root.findall("part"))
    if not base_parts:
        raise ValueError("Page 1 produced no parts")

    # First base <part> per instrument name; later pages' same-instrument
    # systems all continue into this one part.
    first_part_by_name: dict[str, ElementTree.Element] = {}
    for part in base_parts:
        first_part_by_name.setdefault(_part_name(base_root, part.get("id")), part)

    for page_index, tree in enumerate(page_trees[1:], start=2):
        page_root = tree.getroot()
        for page_part in page_root.findall("part"):
            name = _part_name(page_root, page_part.get("id"))
            target = first_part_by_name.get(name)
            if target is None:
                raise ValueError(
                    f"Page {page_index} introduces an instrument not on page 1: {name!r}"
                )
            last_number = max(
                (int(measure.get("number", "0")) for measure in target.findall("measure")),
                default=0,
            )
            for measure in page_part.findall("measure"):
                last_number += 1
                measure.set("number", str(last_number))
                target.append(measure)

    combined = ElementTree.ElementTree(base_root)
    strip_unpaired_repeats(combined)
    return combined


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
        musicxml = pdf_to_musicxml(document)

    output = download_musicXML(musicxml)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
