from __future__ import annotations

import logging
import os
import shutil
from functools import cache
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from colorlog import ColoredFormatter

from libs.common.config import get_settings


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _attach_safe_rotation(handler: TimedRotatingFileHandler) -> None:
    def rotator(source: str, dest: str) -> None:
        dest_path = Path(dest)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(source, dest)
        except FileNotFoundError:
            return
        with open(source, "w", encoding="utf-8"):
            pass

    handler.rotator = rotator


@cache
def setup_logging(bot_name: str) -> logging.Logger:
    _setting = get_settings(bot_name=bot_name, strict=False)

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_file = os.getenv("LOG_FILE", "logs/bot.log")
    backup_days = int(os.getenv("LOG_BACKUP_DAYS", "7"))

    logger = logging.getLogger(bot_name)
    logger.setLevel(log_level)
    logger.propagate = False

    if logger.handlers:
        return logger

    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    console_formatter: ColoredFormatter = ColoredFormatter(
        "%(log_color)s" + fmt,
        datefmt=datefmt,
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold_red",
        },
    )

    ch = logging.StreamHandler()
    ch.setFormatter(console_formatter)
    logger.addHandler(ch)

    log_path = Path(log_file)
    _ensure_dir(log_path)
    fh = TimedRotatingFileHandler(
        str(log_path), when="midnight", backupCount=backup_days, encoding="utf-8", delay=True
    )
    fh.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    _attach_safe_rotation(fh)
    logger.addHandler(fh)
    return logger


__all__ = ["setup_logging"]
