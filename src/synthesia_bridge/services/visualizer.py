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

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOUNDFONT = _PROJECT_ROOT / "piano.sf2"
DEFAULT_AUDIO_SAMPLE_RATE = 44100


class MIDIVisualizerError(RuntimeError):
    """Raised when MIDIVisualizer cannot render the requested video."""


class AudioRenderError(RuntimeError):
    """Raised when audio synthesis or muxing fails."""


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


def _resolve_soundfont(
    soundfont_path: str | Path | None,
) -> Path:
    """Resolve the soundfont path, defaulting to the project-root piano.sf2."""
    candidate = Path(
        soundfont_path or os.environ.get("PIANO_SF2", DEFAULT_SOUNDFONT)
    ).expanduser()
    if not candidate.is_file():
        raise FileNotFoundError(f"Soundfont does not exist: {candidate}")
    return candidate.resolve()


def _validate_render_options(
    width: int,
    height: int,
    framerate: int,
    bitrate: int,
    postroll: float,
    audio_sample_rate: int,
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
    if audio_sample_rate <= 0:
        raise ValueError("audio_sample_rate must be positive")


def midi_to_audio(
    midi_path: str | Path,
    soundfont_path: str | Path,
    output_path: str | Path,
    *,
    sample_rate: int = DEFAULT_AUDIO_SAMPLE_RATE,
) -> Path:
    """Synthesize a MIDI file to WAV using FluidSynth and the provided SF2."""
    soundfont = Path(soundfont_path)
    if not soundfont.is_file():
        raise AudioRenderError(f"SoundFont does not exist: {soundfont}")

    command = [
        "fluidsynth",
        "-ni",
        "-r",
        str(sample_rate),
        "-F",
        str(output_path),
        str(soundfont_path),
        str(midi_path),
    ]

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as error:
        raise FileNotFoundError(
            "Could not execute fluidsynth. Install it and put it on PATH."
        ) from error
    except subprocess.CalledProcessError as error:
        details = (error.stderr or error.stdout or "").strip()
        message = f"fluidsynth failed with exit code {error.returncode}"
        if details:
            message = f"{message}: {details}"
        raise AudioRenderError(message) from error

    output = Path(output_path)
    if not output.is_file() or output.stat().st_size == 0:
        raise AudioRenderError("fluidsynth did not create a WAV file")

    return output


def mux_video_and_audio(
    video_path: str | Path,
    audio_path: str | Path,
    output_path: str | Path,
) -> Path:
    """Mux a silent video and a WAV into an MP4 with AAC audio."""
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-af",
        "apad",
        "-shortest",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        str(output_path),
    ]

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as error:
        raise FileNotFoundError(
            "Could not execute ffmpeg. Install it and put it on PATH."
        ) from error
    except subprocess.CalledProcessError as error:
        details = (error.stderr or error.stdout or "").strip()
        message = f"ffmpeg failed with exit code {error.returncode}"
        if details:
            message = f"{message}: {details}"
        raise AudioRenderError(message) from error

    output = Path(output_path)
    if not output.is_file() or output.stat().st_size == 0:
        raise AudioRenderError("ffmpeg did not create an output file")

    return output


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
    soundfont_path: str | Path | None = None,
    audio_sample_rate: int = DEFAULT_AUDIO_SAMPLE_RATE,
) -> Path:
    """Render a music21 score to an MPEG4 video with MIDIVisualizer.

    MIDIVisualizer consumes a MIDI file rather than an in-memory music21 score.
    The intermediate MIDI and video are staged in a temporary directory, so a
    failed render does not replace an existing output file. Audio is rendered
    from the same MIDI using FluidSynth and muxed into the final MP4.
    """
    _validate_render_options(
        width, height, framerate, bitrate, postroll, audio_sample_rate
    )

    output = Path(output_path).expanduser()
    if output.suffix.lower() != ".mp4":
        raise ValueError("output_path must use the .mp4 extension")
    output.parent.mkdir(parents=True, exist_ok=True)

    visualizer = _resolve_visualizer_executable(visualizer_executable)
    soundfont = _resolve_soundfont(soundfont_path)

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
        staged_audio_path = temporary_directory_path / "audio.wav"
        staged_output_path = temporary_directory_path / "output.mp4"
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

        midi_to_audio(
            midi_path,
            soundfont,
            staged_audio_path,
            sample_rate=audio_sample_rate,
        )
        mux_video_and_audio(staged_video_path, staged_audio_path, staged_output_path)
        staged_output_path.replace(output)

    return output


def main() -> int:
    pdf_path = Path("moonlight-1.pdf")  # Set this to the PDF you want to convert.

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
