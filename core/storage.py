"""
JSON storage helpers.

All intermediate pipeline artefacts live in data/ as pretty-printed JSON so
each stage is inspectable and the pipeline is resumable.
"""

import json

from config import DATA_DIR
from core.logger import get_logger

log = get_logger("storage")


def save_json(filename, payload):
    """Write `payload` to data/<filename> as UTF-8 JSON. Returns the path."""
    path = DATA_DIR / filename
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, default=str)
    log.info("Saved %s (%d bytes)", filename, path.stat().st_size)
    return path


def load_json(filename, default=None):
    """Load data/<filename>. Returns `default` if the file is missing/invalid."""
    path = DATA_DIR / filename
    if not path.exists():
        log.warning("Artefact not found: %s", filename)
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        log.error("Failed to load %s: %s", filename, exc)
        return default
