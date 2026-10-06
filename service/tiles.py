"""Deep Zoom tiles for the reviewer console, built with libvips `dzsave`.

Tiles are keyed by image content, not by study: identical pixels produce identical tiles, and
the key carries no patient information.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from service.storage import Storage

log = logging.getLogger("netrasetu.tiles")

TILE_SIZE = 254
OVERLAP = 1
DZI_NAME = "image.dzi"

_CONTENT_TYPES = {".dzi": "application/xml", ".jpeg": "image/jpeg", ".jpg": "image/jpeg"}


def tiles_prefix(sha_hex: str) -> str:
    return f"tiles/{sha_hex}/"


def build_tiles(image_bytes: bytes) -> dict[str, bytes]:
    """Return {relative path: bytes} for `image.dzi` and `image_files/<level>/<x>_<y>.jpeg`."""
    import pyvips

    image = pyvips.Image.new_from_buffer(image_bytes, "")
    with tempfile.TemporaryDirectory(prefix="nx-tiles-") as tmp:
        base = Path(tmp) / "image"
        image.dzsave(str(base), tile_size=TILE_SIZE, overlap=OVERLAP, suffix=".jpeg[Q=90]")
        root = Path(tmp)
        return {
            p.relative_to(root).as_posix(): p.read_bytes()
            for p in sorted(root.rglob("*"))
            if p.is_file() and p.suffix in _CONTENT_TYPES
        }


def ensure_tiles(storage: Storage, sha_hex: str, image_bytes: bytes) -> None:
    prefix = tiles_prefix(sha_hex)
    if storage.exists(prefix + DZI_NAME):
        return
    try:
        tiles = build_tiles(image_bytes)
    except Exception:  # libvips raises pyvips.Error, import may fail on a broken install
        log.exception("tile generation failed for %s", sha_hex[:12])
        return
    # The .dzi goes last: its presence is what marks the pyramid as complete.
    for rel, data in sorted(tiles.items(), key=lambda kv: kv[0] == DZI_NAME):
        storage.put(prefix + rel, data, _CONTENT_TYPES[Path(rel).suffix])
