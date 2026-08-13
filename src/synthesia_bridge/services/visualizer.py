from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pymupdf as fitz
from music21 import stream

from synthesia_bridge.services.homr_wrapper import pdf_to_musicxml
from synthesia_bridge.services.musicXML_to_midi import download_midi, musicXML_to_midi


DEFAULT_VISUALIZER_EXECUTABLE = "MIDIVisualizer"


class MIDIVisualizerError(RuntimeError):
    """Raised when MIDIVisualizer cannot render the requested video."""


def _resolve_visualizer_executable(
    executable: str | Path | None,
) -> str:
    """Resolve a configured MIDIVisualizer executable or PATH command."""
    executable_name = executable or os.environ.get(
        "MIDIVISUALIZER_BIN", DEFAULT_VISUALIZER_EXECUTABLE
    )
    candidate = Path(executable_name).expanduser()

    if candidate.is_file():
        return str(candidate.resolve())

    if candidate.is_absolute() or candidate.parent != Path("."):
        raise FileNotFoundError(
            f"MIDIVisualizer executable does not exist: {candidate}"
        )

    resolved = shutil.which(str(candidate))
    if resolved is None:
        raise FileNotFoundError(
            "Could not find MIDIVisualizer. Install it and put it on PATH, "
            "or pass its path through MIDIVISUALIZER_BIN."
        )
    return resolved


def _validate_render_options(
    width: int,
    height: int,
    framerate: int,
    bitrate: int,
    postroll: float,
) -> None:
    """Validate values before handing them to the external renderer."""
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    if framerate <= 0:
        raise ValueError("framerate must be positive")
    if bitrate <= 0:
        raise ValueError("bitrate must be positive")
    if postroll < 0:
        raise ValueError("postroll cannot be negative")


def midi_to_video(
    midi: stream.Score,
    output_path: str | Path = "output.mp4",
    visualizer_executable: str | Path | None = None,
    *,
    width: int = 1920,
    height: int = 1080,
    framerate: int = 60,
    bitrate: int = 40,
    postroll: float = 10.0,
    config_path: str | Path | None = None,
) -> Path:
    """Render a music21 score to an MPEG4 video with MIDIVisualizer.

    MIDIVisualizer consumes a MIDI file rather than an in-memory music21 score.
    The intermediate MIDI and video are staged in a temporary directory, so a
    failed render does not replace an existing output file.
    """
    _validate_render_options(width, height, framerate, bitrate, postroll)

    output = Path(output_path).expanduser()
    if output.suffix.lower() != ".mp4":
        raise ValueError("output_path must use the .mp4 extension")
    output.parent.mkdir(parents=True, exist_ok=True)

    visualizer = _resolve_visualizer_executable(visualizer_executable)
    config = None
    if config_path is not None:
        config = Path(config_path).expanduser()
        if not config.is_file():
            raise FileNotFoundError(f"MIDIVisualizer config does not exist: {config}")

    with tempfile.TemporaryDirectory(
        prefix=".synthesia-bridge-", dir=str(output.parent)
    ) as temporary_directory:
        temporary_directory_path = Path(temporary_directory)
        midi_path = temporary_directory_path / "input.mid"
        staged_video_path = temporary_directory_path / "render.mp4"
        download_midi(midi, midi_path)

        command = [
            visualizer,
            "--midi",
            str(midi_path),
            "--export",
            str(staged_video_path),
            "--format",
            "MPEG4",
            "--size",
            str(width),
            str(height),
            "--framerate",
            str(framerate),
            "--bitrate",
            str(bitrate),
            "--postroll",
            str(postroll),
            "--hide-window",
            "1",
        ]
        if config is not None:
            command.extend(["--config", str(config)])

        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as error:
            raise FileNotFoundError(
                f"Could not execute MIDIVisualizer: {visualizer}"
            ) from error
        except subprocess.CalledProcessError as error:
            details = (error.stderr or error.stdout or "").strip()
            message = f"MIDIVisualizer failed with exit code {error.returncode}"
            if details:
                message = f"{message}: {details}"
            raise MIDIVisualizerError(message) from error

        if not staged_video_path.is_file():
            stdout = (completed.stdout or "").strip()
            details = f": {stdout}" if stdout else ""
            raise MIDIVisualizerError(
                f"MIDIVisualizer completed without creating {staged_video_path.name}"
                f"{details}"
            )
        if staged_video_path.stat().st_size == 0:
            raise MIDIVisualizerError("MIDIVisualizer created an empty video")

        staged_video_path.replace(output)

    return output


def main() -> int:
    pdf_path = Path("winter-wind.pdf")  # Set this to the PDF you want to convert.

    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")

    with fitz.open(pdf_path) as document:
        musicxml = pdf_to_musicxml(document)

    midi = musicXML_to_midi(musicxml)
    output = midi_to_video(midi)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
