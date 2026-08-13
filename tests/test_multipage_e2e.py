"""End-to-end test for the multi-page PDF -> MusicXML -> MIDI pipeline.

Composes a 2-page PDF from pages 1 and 8 of the real ``moonlight.pdf``
fixture. Those two pages reproduce the real-world failure that motivated the
merge logic: HOMR emits page 1 as a single Piano ``<part>`` but page 8 as two
Piano ``<part>`` elements (two grand-staff systems). ``pdf_to_musicxml`` must
consolidate them into one continuous Piano part. The combined score's note and
measure counts must equal the sum of each page processed independently.

Marked ``e2e`` and skipped by default; run explicitly::

    python -m pytest tests/ -m e2e
"""

from pathlib import Path

import pymupdf as fitz
import pytest
from music21 import stream

from synthesia_bridge.services.homr_wrapper import pdf_to_musicxml
from synthesia_bridge.services.musicXML_to_midi import musicXML_to_midi

MULTIPAGE_PDF = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "synthesia_bridge"
    / "services"
    / "moonlight.pdf"
)
# Page numbers (1-based) chosen to reproduce the variable-part-count case:
# page 1 -> one Piano part, page 8 -> two Piano parts.
COMPOSED_PAGES = (1, 8)


def _score_from_pages(pdf: Path, page_numbers: tuple[int, ...]) -> stream.Score:
    composed = fitz.open()
    try:
        with fitz.open(str(pdf)) as source:
            for page_number in page_numbers:
                composed.insert_pdf(source, from_page=page_number - 1, to_page=page_number - 1)
        return musicXML_to_midi(pdf_to_musicxml(composed))
    finally:
        composed.close()


def _note_count(score: stream.Score) -> int:
    return len(list(score.recurse().notes))


def _measure_count(score: stream.Score) -> int:
    return sum(len(part.getElementsByClass(stream.Measure)) for part in score.parts)


@pytest.mark.e2e
def test_multipage_pdf_consolidates_variable_part_counts() -> None:
    combined_score = _score_from_pages(MULTIPAGE_PDF, COMPOSED_PAGES)
    first_page_score = _score_from_pages(MULTIPAGE_PDF, (COMPOSED_PAGES[0],))
    second_page_score = _score_from_pages(MULTIPAGE_PDF, (COMPOSED_PAGES[1],))

    assert _note_count(combined_score) == _note_count(first_page_score) + _note_count(
        second_page_score
    )
    assert _measure_count(combined_score) == _measure_count(first_page_score) + _measure_count(
        second_page_score
    )


@pytest.mark.e2e
def test_multipage_pdf_with_unpaired_repeats_exports_midi(tmp_path: Path) -> None:
    """HOMR emits backward-only repeats on moonlight.pdf pages 7 and 12.

    Before the ``strip_unpaired_repeats`` band-aid, those unpaired backwards
    made music21's repeat-expansion raise ``ExpanderException`` during MIDI
    export. Compose a 2-page PDF from those pages and assert the full pipeline
    still exports a non-empty ``.mid`` file.
    """
    from synthesia_bridge.services.musicXML_to_midi import download_midi

    score = _score_from_pages(MULTIPAGE_PDF, (7, 12))
    output_path = tmp_path / "moonlight_repeats.mid"

    download_midi(score, output_path)

    assert output_path.is_file()
    assert output_path.read_bytes().startswith(b"MThd")
    assert output_path.stat().st_size > 0