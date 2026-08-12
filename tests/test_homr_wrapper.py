from pathlib import Path

import fitz

from synthesia_bridge.services.homr_wrapper import pdf_page_to_image, pdf_page_to_musicxml


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
