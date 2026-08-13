import os
import subprocess
from pathlib import Path

import pytest
from music21 import note, stream

from synthesia_bridge.services.visualizer import MIDIVisualizerError, midi_to_video


def simple_score() -> stream.Score:
    score = stream.Score()
    part = stream.Part()
    part.append(note.Note("C4", quarterLength=1))
    score.insert(0, part)
    return score


def visualizer_executable(tmp_path: Path) -> Path:
    executable = tmp_path / "MIDIVisualizer"
    executable.write_text("placeholder")
    return executable


def test_midi_to_video_serializes_midi_and_runs_visualizer(
    tmp_path: Path, monkeypatch
) -> None:
    command = None
    midi_data = None
    output = tmp_path / "nested" / "score.mp4"

    def fake_run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
        nonlocal command, midi_data
        command = args
        midi_path = Path(args[args.index("--midi") + 1])
        midi_data = midi_path.read_bytes()
        video_path = Path(args[args.index("--export") + 1])
        video_path.write_bytes(b"....ftypfake-mp4")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(
        "synthesia_bridge.services.visualizer.subprocess.run", fake_run
    )

    result = midi_to_video(
        simple_score(),
        output,
        visualizer_executable(tmp_path),
        width=640,
        height=360,
        framerate=30,
        bitrate=12,
        postroll=2.5,
    )

    assert result == output
    assert output.read_bytes() == b"....ftypfake-mp4"
    assert midi_data is not None and midi_data.startswith(b"MThd")
    assert command is not None
    assert command[command.index("--format") + 1] == "MPEG4"
    assert command[command.index("--size") + 1 : command.index("--size") + 3] == [
        "640",
        "360",
    ]
    assert command[-2:] == ["--hide-window", "1"]


def test_midi_to_video_does_not_replace_output_when_render_fails(
    tmp_path: Path, monkeypatch
) -> None:
    output = tmp_path / "score.mp4"
    output.write_bytes(b"previous video")

    def fake_run(args: list[str], **kwargs) -> None:
        raise subprocess.CalledProcessError(
            2, args, stderr="video export is unavailable"
        )

    monkeypatch.setattr(
        "synthesia_bridge.services.visualizer.subprocess.run", fake_run
    )

    with pytest.raises(MIDIVisualizerError, match="video export is unavailable"):
        midi_to_video(simple_score(), output, visualizer_executable(tmp_path))

    assert output.read_bytes() == b"previous video"


def test_midi_to_video_requires_rendered_output(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "score.mp4"

    def fake_run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(args, 0, stdout="finished", stderr="")

    monkeypatch.setattr(
        "synthesia_bridge.services.visualizer.subprocess.run", fake_run
    )

    with pytest.raises(MIDIVisualizerError, match="without creating"):
        midi_to_video(simple_score(), output, visualizer_executable(tmp_path))

    assert not output.exists()


def test_midi_to_video_reports_missing_visualizer(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="executable does not exist"):
        midi_to_video(
            simple_score(),
            tmp_path / "score.mp4",
            tmp_path / "missing" / "MIDIVisualizer",
        )


@pytest.mark.e2e
def test_midi_to_video_with_installed_visualizer(tmp_path: Path) -> None:
    executable = os.environ.get("MIDIVISUALIZER_BIN")
    if not executable:
        pytest.skip("set MIDIVISUALIZER_BIN to run the MIDIVisualizer e2e test")

    output = midi_to_video(
        simple_score(),
        tmp_path / "score.mp4",
        executable,
        width=128,
        height=128,
        framerate=1,
        bitrate=1,
        postroll=0,
    )

    data = output.read_bytes()
    assert len(data) > 8
    assert data[4:8] == b"ftyp"
