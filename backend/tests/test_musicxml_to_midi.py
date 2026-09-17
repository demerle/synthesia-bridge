from xml.etree import ElementTree

from synthesia_bridge.services.musicXML_to_midi import download_midi, musicXML_to_midi


def musicxml_document() -> ElementTree.ElementTree:
    return ElementTree.ElementTree(
        ElementTree.fromstring(
            """
            <score-partwise version="4.0">
              <part-list>
                <score-part id="P1"><part-name>Piano</part-name></score-part>
              </part-list>
              <part id="P1">
                <measure number="1">
                  <attributes>
                    <divisions>1</divisions>
                    <key><fifths>0</fifths></key>
                    <time><beats>4</beats><beat-type>4</beat-type></time>
                    <clef><sign>G</sign><line>2</line></clef>
                  </attributes>
                  <note>
                    <pitch><step>C</step><octave>4</octave></pitch>
                    <duration>1</duration>
                    <type>quarter</type>
                  </note>
                </measure>
              </part>
            </score-partwise>
            """
        )
    )


def test_musicxml_to_midi_returns_score() -> None:
    score = musicXML_to_midi(musicxml_document())

    assert score.parts[0].recurse().notes.first().pitch.nameWithOctave == "C4"


def test_download_midi_writes_requested_path(tmp_path) -> None:
    output = tmp_path / "nested" / "score.mid"
    score = musicXML_to_midi(musicxml_document())

    result = download_midi(score, output)

    assert result == output
    assert output.read_bytes().startswith(b"MThd")
