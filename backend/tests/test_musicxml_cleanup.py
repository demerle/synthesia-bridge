"""Unit tests for the HOMR repeat-cleanup band-aid.

These build real MusicXML trees with ElementTree (no mocks) per AGENTS.md and
exercise the four behaviours of ``strip_unpaired_repeats`` directly.
"""

from xml.etree import ElementTree

from synthesia_bridge.services.musicxml_cleanup import strip_unpaired_repeats


def _measure_with_direction(number: int, direction: str) -> ElementTree.Element:
    """Build a <measure> holding a <barline> with one <repeat direction=...>."""
    measure = ElementTree.Element("measure", number=str(number))
    ElementTree.SubElement(measure, "note")
    barline = ElementTree.SubElement(measure, "barline")
    ElementTree.SubElement(barline, "repeat", direction=direction)
    return measure


def _tree_with_measures(measures: list[ElementTree.Element]) -> ElementTree.ElementTree:
    """Wrap measures in a <part id='P1'> inside a <score-partwise> root."""
    root = ElementTree.Element("score-partwise")
    part_list = ElementTree.SubElement(root, "part-list")
    ElementTree.SubElement(part_list, "score-part", id="P1")
    part = ElementTree.SubElement(root, "part", id="P1")
    for measure in measures:
        part.append(measure)
    return ElementTree.ElementTree(root)


def _repeat_directions(tree: ElementTree.ElementTree) -> list[tuple[str, str]]:
    """Return (measure number, repeat direction) for all repeats, in order."""
    result = []
    for part in tree.getroot().findall("part"):
        for measure in part.findall("measure"):
            for bar in measure.findall("barline"):
                repeat = bar.find("repeat")
                if repeat is not None:
                    result.append((measure.get("number", ""), repeat.get("direction", "")))
    return result


def test_strip_removes_unmatched_backward_repeat() -> None:
    # Measure 1: forward repeat. Measure 2: matched backward (kept).
    # Measure 3: unpaired backward (must be removed).
    measures = [
        _measure_with_direction(1, "forward"),
        _measure_with_direction(2, "backward"),
        _measure_with_direction(3, "backward"),
    ]
    tree = _tree_with_measures(measures)

    strip_unpaired_repeats(tree)

    assert _repeat_directions(tree) == [("1", "forward"), ("2", "backward")]


def test_strip_preserves_paired_repeats() -> None:
    # Two independent forward/backward pairs should all survive untouched.
    measures = [
        _measure_with_direction(1, "forward"),
        _measure_with_direction(2, "backward"),
        _measure_with_direction(3, "forward"),
        _measure_with_direction(4, "backward"),
    ]
    tree = _tree_with_measures(measures)

    strip_unpaired_repeats(tree)

    assert _repeat_directions(tree) == [
        ("1", "forward"),
        ("2", "backward"),
        ("3", "forward"),
        ("4", "backward"),
    ]


def test_strip_keeps_barline_with_other_children() -> None:
    # A barline that carries both a backward <repeat> and a <bar-style>
    # must lose only the <repeat>; the <barline> and <bar-style> stay.
    measure = ElementTree.Element("measure", number="1")
    ElementTree.SubElement(measure, "note")
    barline = ElementTree.SubElement(measure, "barline", location="right")
    ElementTree.SubElement(barline, "repeat", direction="backward")
    bar_style = ElementTree.SubElement(barline, "bar-style")
    bar_style.text = "light-heavy"
    tree = _tree_with_measures([measure])

    strip_unpaired_repeats(tree)

    barline_after = tree.getroot().find(".//measure[@number='1']/barline")
    assert barline_after is not None, "<barline> must survive (still holds <bar-style>)"
    assert barline_after.find("repeat") is None, "unpaired backward <repeat> must be removed"
    assert barline_after.findtext("bar-style") == "light-heavy"


def test_strip_handles_multiple_parts_independently() -> None:
    # Part A opens a forward repeat; part B's backward repeat is unpaired
    # relative to part B. The forward in part A must not cancel part B's
    # unmatched backward, since each part keeps its own open-forward count.
    root = ElementTree.Element("score-partwise")
    part_list = ElementTree.SubElement(root, "part-list")
    ElementTree.SubElement(part_list, "score-part", id="P1")
    ElementTree.SubElement(part_list, "score-part", id="P2")
    part_a = ElementTree.SubElement(root, "part", id="P1")
    part_b = ElementTree.SubElement(root, "part", id="P2")
    part_a.append(_measure_with_direction(1, "forward"))

    measure_b = ElementTree.Element("measure", number="1")
    ElementTree.SubElement(measure_b, "note")
    barline_b = ElementTree.SubElement(measure_b, "barline")
    ElementTree.SubElement(barline_b, "repeat", direction="backward")
    part_b.append(measure_b)
    tree = ElementTree.ElementTree(root)

    strip_unpaired_repeats(tree)

    part_a_repeats = part_a.findall(".//repeat")
    part_b_repeats = part_b.findall(".//repeat")
    assert len(part_a_repeats) == 1
    assert part_a_repeats[0].get("direction") == "forward"
    assert len(part_b_repeats) == 0