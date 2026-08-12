from xml.etree import ElementTree

from synthesia_bridge.services.homr_wrapper import download_musicXML


def test_download_musicxml_writes_requested_path(tmp_path) -> None:
    document = ElementTree.ElementTree(ElementTree.Element("score-partwise"))
    output = tmp_path / "score.musicxml"

    result = download_musicXML(document, output)

    assert result == output
    assert ElementTree.parse(output).getroot().tag == "score-partwise"
