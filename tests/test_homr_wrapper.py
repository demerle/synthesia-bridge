from pathlib import Path

import fitz
import pytest

from synthesia_bridge.services.homr_wrapper import (
    pdf_page_to_image,
    pdf_page_to_musicxml,
    pdf_to_musicxml,
)


def _piano_part_musicxml(measure_numbers: list[int]) -> str:
    """One <part> named Piano with the given measures, plus its <part-list>."""
    measures = ""
    for number in measure_numbers:
        measures += f"<measure number='{number}'><note><rest/></note></measure>"
    return (
        "<?xml version='1.0'?><score-partwise>"
        "<part-list><score-part id='P1'>"
        "<part-name>Piano</part-name>"
        "</score-part></part-list>"
        f"<part id='P1'>{measures}</part>"
        "</score-partwise>"
    )


def _two_piano_parts_musicxml() -> str:
    """Two <part> elements, both named Piano (two grand-staff systems)."""
    return (
        "<?xml version='1.0'?><score-partwise>"
        "<part-list>"
        "<score-part id='P1'><part-name>Piano</part-name></score-part>"
        "<score-part id='P2'><part-name>Piano</part-name></score-part>"
        "</part-list>"
        "<part id='P1'><measure number='1'><note><rest/></note></measure></part>"
        "<part id='P2'><measure number='1'><note><rest/></note></measure></part>"
        "</score-partwise>"
    )


def _piano_and_voice_musicxml() -> str:
    """A Piano part and a Voice part on the same page."""
    return (
        "<?xml version='1.0'?><score-partwise>"
        "<part-list>"
        "<score-part id='P1'><part-name>Piano</part-name></score-part>"
        "<score-part id='P2'><part-name>Voice</part-name></score-part>"
        "</part-list>"
        "<part id='P1'><measure number='1'><note><rest/></note></measure></part>"
        "<part id='P2'><measure number='1'><note><rest/></note></measure></part>"
        "</score-partwise>"
    )


def test_pdf_to_image_returns_png_bytes() -> None:
    document = fitz.open()
    page = document.new_page()

    image = pdf_page_to_image(page)

    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    document.close()


def test_pdf_to_musicxml_runs_homr_and_parses_output(monkeypatch) -> None:
    document = fitz.open()
    page = document.new_page()
    command = None

    def fake_run(args: list[str], check: bool) -> None:
        nonlocal command
        command = args
        output_path = Path(args[-1]).with_suffix(".musicxml")
        output_path.write_text("<?xml version='1.0'?><score-partwise />")
        assert check is True

    monkeypatch.setattr("synthesia_bridge.services.homr_wrapper.subprocess.run", fake_run)

    musicxml = pdf_page_to_musicxml(page)

    assert command is not None
    assert command[1:3] == ["-m", "homr.main"]
    assert command[-1].endswith("page.png")
    assert musicxml.getroot().tag == "score-partwise"
    document.close()


def test_pdf_to_musicxml_requires_homr_output(monkeypatch) -> None:
    document = fitz.open()
    page = document.new_page()
    monkeypatch.setattr(
        "synthesia_bridge.services.homr_wrapper.subprocess.run",
        lambda args, check: None,
    )

    try:
        pdf_page_to_musicxml(page)
    except FileNotFoundError as error:
        assert str(error) == "HOMR did not create page.musicxml"
    else:
        raise AssertionError("pdf_to_musicxml should require HOMR output")
    finally:
        document.close()


def test_pdf_to_musicxml_merges_all_pages(monkeypatch) -> None:
    document = fitz.open()
    document.new_page()
    document.new_page()

    def fake_run(args: list[str], check: bool) -> None:
        output_path = Path(args[-1]).with_suffix(".musicxml")
        output_path.write_text(_piano_part_musicxml([1]))
        assert check is True

    monkeypatch.setattr("synthesia_bridge.services.homr_wrapper.subprocess.run", fake_run)

    musicxml = pdf_to_musicxml(document)

    root = musicxml.getroot()
    parts = root.findall("part")
    assert len(parts) == 1, "combined document should keep a single part"

    measures = parts[0].findall("measure")
    assert [m.get("number") for m in measures] == ["1", "2"]
    document.close()


def test_pdf_to_musicxml_consolidates_extra_same_instrument_part(monkeypatch) -> None:
    # Reproduces the moonlight.pdf failure: page 1 has one Piano part but page 8
    # has two Piano parts (two grand-staff systems). Both must merge into one.
    document = fitz.open()
    document.new_page()
    document.new_page()

    call_count = 0

    def fake_run(args: list[str], check: bool) -> None:
        nonlocal call_count
        call_count += 1
        output_path = Path(args[-1]).with_suffix(".musicxml")
        if call_count == 1:
            output_path.write_text(_piano_part_musicxml([1]))
        else:
            output_path.write_text(_two_piano_parts_musicxml())
        assert check is True

    monkeypatch.setattr("synthesia_bridge.services.homr_wrapper.subprocess.run", fake_run)

    musicxml = pdf_to_musicxml(document)

    root = musicxml.getroot()
    parts = root.findall("part")
    assert len(parts) == 1, "two same-instrument parts must consolidate into one"

    measures = parts[0].findall("measure")
    assert [m.get("number") for m in measures] == ["1", "2", "3"]
    document.close()


def test_pdf_to_musicxml_rejects_new_instrument(monkeypatch) -> None:
    # A page introducing an instrument absent from page 1 must surface loudly.
    document = fitz.open()
    document.new_page()
    document.new_page()

    call_count = 0

    def fake_run(args: list[str], check: bool) -> None:
        nonlocal call_count
        call_count += 1
        output_path = Path(args[-1]).with_suffix(".musicxml")
        if call_count == 1:
            output_path.write_text(_piano_part_musicxml([1]))
        else:
            output_path.write_text(_piano_and_voice_musicxml())
        assert check is True

    monkeypatch.setattr("synthesia_bridge.services.homr_wrapper.subprocess.run", fake_run)

    with pytest.raises(ValueError, match="introduces an instrument"):
        pdf_to_musicxml(document)
    document.close()


def test_pdf_to_musicxml_rejects_empty_pdf() -> None:
    document = fitz.open()

    with pytest.raises(ValueError, match="any pages"):
        pdf_to_musicxml(document)
    document.close()
