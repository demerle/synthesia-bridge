#!/usr/bin/env python3
"""Run HOMR on one PNG and verify that MusicXML was created."""

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert one PNG sheet-music image with HOMR")
    parser.add_argument("image", type=Path, help="Path to a PNG sheet-music image")
    args = parser.parse_args()

    image = args.image
    if not image.is_file():
        parser.error(f"input file does not exist: {image}")
    if image.suffix.lower() != ".png":
        parser.error("input file must be a PNG")

    subprocess.run([sys.executable, "-m", "homr.main", str(image)], check=True)

    musicxml = image.with_suffix(".musicxml")
    if not musicxml.is_file():
        raise RuntimeError(f"HOMR finished without creating {musicxml}")

    print(musicxml)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
