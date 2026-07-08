"""
Logging setup for the pipeline.

One timestamped log file per run in logs/, plus a console stream.
File captures DEBUG and above; console shows INFO and above so the
terminal stays readable while the file keeps the full trace.
"""

import logging
import sys
from datetime import datetime

from config import LOGS_DIR

_CONFIGURED = False
_RUN_LOG_PATH = None


def setup_logging(level_console=logging.INFO, level_file=logging.DEBUG):
    """Configure the root logger once. Returns the path of this run's log file."""
    global _CONFIGURED, _RUN_LOG_PATH
    if _CONFIGURED:
        return _RUN_LOG_PATH

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    _RUN_LOG_PATH = LOGS_DIR / f"run_{timestamp}.log"

    # Windows consoles default to cp1252 and crash on accented player names or
    # the U+2212 minus sign Wikipedia uses in scores. Force UTF-8 with a safe
    # fallback so logging never takes the pipeline down.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)-18s | %(message)s",
        datefmt="%H:%M:%S",
    )

    file_handler = logging.FileHandler(_RUN_LOG_PATH, encoding="utf-8")
    file_handler.setLevel(level_file)
    file_handler.setFormatter(fmt)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level_console)
    console_handler.setFormatter(fmt)

    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # Quieten noisy third-party loggers.
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    _CONFIGURED = True
    logging.getLogger("logger").info("Logging initialised -> %s", _RUN_LOG_PATH)
    return _RUN_LOG_PATH


def get_logger(name):
    """Get a named logger (ensures logging is configured first)."""
    setup_logging()
    return logging.getLogger(name)
