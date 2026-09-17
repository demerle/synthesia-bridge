import os
import subprocess
from pathlib import Path

import pytest
from music21 import converter, note, stream, tempo

from synthesia_bridge.services.visualizer import (
    AudioRenderError,
    MIDIVisualizerError,
    midi_to_video,
)


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


def _find_flag(args: list[str], flag: str) -> str:
    """Return the value immediately following *flag* in a command list."""
    index = args.index(flag)
    return args[index + 1]


def _make_fake_subprocess(
    visualizer_path: Path,
    *,
    fail_ffmpeg: bool = False,
    fail_fluidsynth: bool = False,
):
    """Return a fake subprocess.run that creates expected output files."""

    def fake_run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
        executable = args[0]

        if Path(executable).resolve() == visualizer_path.resolve():
            video_path = Path(_find_flag(args, "--export"))
            video_path.write_bytes(b"....ftypfake-mp4")
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        if executable == "fluidsynth":
            if fail_fluidsynth:
                raise subprocess.CalledProcessError(
                    1, args, stderr="fluidsynth is broken"
                )
            wav_path = Path(_find_flag(args, "-F"))
            wav_path.write_bytes(b"RIFF....WAVE....data....")
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        if executable == "ffmpeg":
            if fail_ffmpeg:
                raise subprocess.CalledProcessError(
                    1, args, stderr="muxing is unavailable"
                )
            output_path = Path(args[-1])
            output_path.write_bytes(b"....ftypmuxed-mp4")
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        raise AssertionError(f"unexpected command in test: {args}")

    return fake_run


def test_midi_to_video_serializes_midi_and_runs_visualizer(
    tmp_path: Path, monkeypatch
) -> None:
    midi_data = None
    output = tmp_path / "nested" / "score.mp4"
    executable = visualizer_executable(tmp_path)
    fake_run = _make_fake_subprocess(executable)
    monkeypatch.setattr("synthesia_bridge.services.visualizer.subprocess.run", fake_run)

    soundfont = tmp_path / "dummy.sf2"
    soundfont.write_bytes(b"dummy soundfont")

    result = midi_to_video(
        simple_score(),
        output,
        executable,
        width=640,
        height=360,
        framerate=30,
        bitrate=12,
        postroll=2.5,
        soundfont_path=soundfont,
    )

    assert result == output
    assert output.read_bytes() == b"....ftypmuxed-mp4"
    assert output.read_bytes() is not None


def test_midi_to_video_invokes_fluidsynth_and_ffmpeg(
    tmp_path: Path, monkeypatch
) -> None:
    commands: list[list[str]] = []
    executable = visualizer_executable(tmp_path)
    soundfont = tmp_path / "dummy.sf2"
    soundfont.write_bytes(b"dummy soundfont")

    def tracking_run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
        commands.append(list(args))
        return _make_fake_subprocess(executable)(args, **kwargs)

    monkeypatch.setattr(
        "synthesia_bridge.services.visualizer.subprocess.run", tracking_run
    )

    midi_to_video(
        simple_score(),
        tmp_path / "score.mp4",
        executable,
        soundfont_path=soundfont,
    )

    fluidsynth_command = next(c for c in commands if c[0] == "fluidsynth")
    ffmpeg_command = next(c for c in commands if c[0] == "ffmpeg")

    assert fluidsynth_command[fluidsynth_command.index("-sf2") + 1] == str(soundfont)
    assert "-F" in fluidsynth_command
    assert "-r" in fluidsynth_command

    assert ffmpeg_command[ffmpeg_command.index("-c:v") + 1] == "copy"
    assert ffmpeg_command[ffmpeg_command.index("-c:a") + 1] == "aac"
    assert "apad" in ffmpeg_command
    assert "-shortest" in ffmpeg_command


def test_midi_to_video_does_not_replace_output_when_visualizer_fails(
    tmp_path: Path, monkeypatch
) -> None:
    output = tmp_path / "score.mp4"
    output.write_bytes(b"previous video")

    def fake_run(args: list[str], **kwargs) -> None:
        raise subprocess.CalledProcessError(
            2, args, stderr="video export is unavailable"
        )

    monkeypatch.setattr("synthesia_bridge.services.visualizer.subprocess.run", fake_run)

    with pytest.raises(MIDIVisualizerError, match="video export is unavailable"):
        midi_to_video(simple_score(), output, visualizer_executable(tmp_path))

    assert output.read_bytes() == b"previous video"


def test_midi_to_video_does_not_replace_output_when_audio_render_fails(
    tmp_path: Path, monkeypatch
) -> None:
    output = tmp_path / "score.mp4"
    output.write_bytes(b"previous video")
    executable = visualizer_executable(tmp_path)

    fake_run = _make_fake_subprocess(executable, fail_fluidsynth=True)
    monkeypatch.setattr("synthesia_bridge.services.visualizer.subprocess.run", fake_run)

    with pytest.raises(AudioRenderError, match="fluidsynth is broken"):
        midi_to_video(simple_score(), output, executable)

    assert output.read_bytes() == b"previous video"


def test_midi_to_video_does_not_replace_output_when_muxing_fails(
    tmp_path: Path, monkeypatch
) -> None:
    output = tmp_path / "score.mp4"
    output.write_bytes(b"previous video")
    executable = visualizer_executable(tmp_path)

    fake_run = _make_fake_subprocess(executable, fail_ffmpeg=True)
    monkeypatch.setattr("synthesia_bridge.services.visualizer.subprocess.run", fake_run)

    with pytest.raises(AudioRenderError, match="muxing is unavailable"):
        midi_to_video(simple_score(), output, executable)

    assert output.read_bytes() == b"previous video"


def test_midi_to_video_reports_missing_visualizer(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="executable does not exist"):
        midi_to_video(
            simple_score(),
            tmp_path / "score.mp4",
            tmp_path / "missing" / "MIDIVisualizer",
        )


def test_midi_to_video_reports_missing_soundfont(tmp_path: Path) -> None:
    executable = visualizer_executable(tmp_path)
    with pytest.raises(FileNotFoundError, match="Soundfont does not exist"):
        midi_to_video(
            simple_score(),
            tmp_path / "score.mp4",
            executable,
            soundfont_path=tmp_path / "missing.sf2",
        )


def test_midi_to_video_requires_rendered_output(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "score.mp4"

    def fake_run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(args, 0, stdout="finished", stderr="")

    monkeypatch.setattr("synthesia_bridge.services.visualizer.subprocess.run", fake_run)

    with pytest.raises(MIDIVisualizerError, match="without creating"):
        midi_to_video(simple_score(), output, visualizer_executable(tmp_path))

    assert not output.exists()


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

    ffprobe_result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name",
            "-of",
            "default=noprint_wrappers=1",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "codec_name=aac" in ffprobe_result.stdout


def test_tempo_override_sets_written_midi_tempo(tmp_path: Path) -> None:
    """A score rendered with tempo_bpm keeps the requested tempo in the MIDI.

    END-TO-END via a real MIDI file round trip, no mocks: write the MIDI
    exactly as midi_to_video() does, then re-read it and inspect the tempo.
    """
    from synthesia_bridge.services.visualizer import _apply_tempo

    score = simple_score()
    score.insert(0, tempo.MetronomeMark(number=240))

    rendered = _apply_tempo(score, 72)
    output_path = tmp_path / "out.mid"
    rendered.write("midi", fp=str(output_path))

    score_back = converter.parse(str(output_path), format="midi")
    marks = list(score_back.recurse().getElementsByClass(tempo.MetronomeMark))
    assert len(marks) == 1
    assert marks[0].number == 72


def test_tempo_override_keeps_score_when_not_requested() -> None:
    from synthesia_bridge.services.visualizer import _apply_tempo

    score = simple_score()
    original = tempo.MetronomeMark(number=90)
    score.insert(0, original)

    _apply_tempo(score, None)

    marks = list(score.recurse().getElementsByClass(tempo.MetronomeMark))
    assert len(marks) == 1
    assert marks[0].number == 90


def test_tempo_override_rejects_bad_values(tmp_path: Path) -> None:
    executable = visualizer_executable(tmp_path)
    soundfont = tmp_path / "dummy.sf2"
    soundfont.write_bytes(b"dummy soundfont")

    with pytest.raises(ValueError):
        midi_to_video(
            simple_score(),
            tmp_path / "out.mp4",
            executable,
            soundfont_path=soundfont,
            tempo_bpm=999,
        )
