"""Defensive cleanup of HOMR's MusicXML output.

HOMR (https://github.com/liebharc/homr) occasionally emits
``<repeat direction="backward">`` barlines with no matching forward repeat in
the same <part>. music21 raises ``ExpanderException`` when it tries to expand
those repeats during MIDI export, which would otherwise abort the whole
PDF -> MusicXML -> MIDI pipeline on real-world scores.

This module strips the unpaired backward repeats before the music21 conversion
sees them. Paired forward/backward repeats are kept untouched, so this is a
no-op once (if ever) HOMR fixes the upstream detection.
"""

from xml.etree import ElementTree


def strip_unpaired_repeats(tree: ElementTree.ElementTree) -> None:
    """Remove backward-repeat barlines that have no matching forward repeat.

    Walks each <part>'s measures in document order, pairing backwards only with
    surviving open forwards; drops any backward with no open forward, and the
    <barline> wrapper if it becomes empty. Endings and other barline children
    stay in place.
    """
    for part in tree.getroot().findall("part"):
        _strip_unpaired_in_part(part)


def _strip_unpaired_in_part(part: ElementTree.Element) -> None:
    open_forwards = 0
    for measure in part.findall("measure"):
        for barline in list(measure.findall("barline")):
            repeat = barline.find("repeat")
            if repeat is None:
                continue
            direction = repeat.get("direction", "")
            if direction == "forward":
                open_forwards += 1
            elif direction == "backward" and open_forwards == 0:
                barline.remove(repeat)
                if len(list(barline)) == 0:
                    measure.remove(barline)
            elif direction == "backward":
                open_forwards -= 1