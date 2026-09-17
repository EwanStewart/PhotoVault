"""Rasterise the home-screen icons from the logo.

static/icons/logo.svg is the source of truth. This renders it once with
headless Chrome, the only SVG renderer on the box, then derives every size
the manifest and iOS ask for. Run from the repo root after editing the logo:

    venv/bin/python scripts/make_icons.py

Rounded icons keep transparent corners. The iOS touch icon and the maskable
icon stay fully opaque, because iOS paints a transparent touch icon onto
black and Android crops a maskable icon to its own shape. The maskable icon
is inset so the motif survives that crop.
"""

import subprocess
import tempfile
from pathlib import Path

BRAND = "#12131a"
CHROME = "google-chrome"
MASTER_SIZE = 1024
MASKABLE_SAFE_FRACTION = 0.8
ICON_DIR = (
    Path(__file__).resolve().parent.parent
    / "src" / "photovault" / "static" / "icons"
)
LOGO = ICON_DIR / "logo.svg"


def render_master(destination: Path) -> None:
    """Rasterise the logo at full size with headless Chrome."""
    command = [
        CHROME,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        "--default-background-color=00000000",
        f"--screenshot={destination}",
        f"--window-size={MASTER_SIZE},{MASTER_SIZE}",
        str(LOGO),
    ]
    subprocess.run(command, check=True, capture_output=True)


def write_rounded(master: Path, size: int, destination: Path) -> None:
    """Resize the master to one size, keeping the transparent corners."""
    command = [
        "convert", str(master),
        "-resize", f"{size}x{size}",
        "-colorspace", "sRGB",
        "-depth", "8",
        str(destination),
    ]
    subprocess.run(command, check=True)


def write_opaque(master: Path, size: int, inset: float, destination: Path) -> None:
    """Resize the master onto an opaque brand square, inset by the given fraction."""
    motif = round(size * inset)
    command = [
        "convert", str(master),
        "-resize", f"{motif}x{motif}",
        "-background", BRAND,
        "-gravity", "center",
        "-extent", f"{size}x{size}",
        "-alpha", "remove",
        "-alpha", "off",
        "-colorspace", "sRGB",
        "-depth", "8",
        str(destination),
    ]
    subprocess.run(command, check=True)


def main() -> None:
    """Write every icon the manifest and the iOS touch icon reference."""
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as workspace:
        master = Path(workspace) / "master.png"
        render_master(master)
        write_rounded(master, 192, ICON_DIR / "icon-192.png")
        write_rounded(master, 512, ICON_DIR / "icon-512.png")
        write_opaque(master, 180, 1.0, ICON_DIR / "apple-touch-icon.png")
        write_opaque(master, 512, MASKABLE_SAFE_FRACTION,
                     ICON_DIR / "icon-maskable-512.png")


if __name__ == "__main__":
    main()
