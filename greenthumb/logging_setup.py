from __future__ import annotations

import logging
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "greenthumb.log"


def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("greenthumb")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    # datefmt drops the ",mmm" logging appends to asctime by default. Nothing
    # here happens on a millisecond scale -- the control loop ticks once a
    # minute and a dose runs for tens of seconds -- so the digits were noise in
    # every line of the Logs tab.
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def read_recent_logs(lines: int = 200) -> list[str]:
    if not LOG_FILE.exists():
        return []

    with LOG_FILE.open("r", encoding="utf-8") as log_file:
        entries = log_file.readlines()

    return entries[-max(1, lines) :]


def log_event(message: str, level: int = logging.INFO) -> None:
    logger = setup_logging()
    logger.log(level, message)
