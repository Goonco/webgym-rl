import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.logging import RichHandler


def _setup_runtime_logger() -> logging.Logger:
    logger = logging.getLogger("webgym-rl.runtime")
    logger.propagate = False

    if logger.handlers:
        return logger

    console_handler = RichHandler(rich_tracebacks=True)
    console_handler.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))

    logger.addHandler(console_handler)
    return logger


def _setup_file_logger(
    log_path: Path,
) -> None:
    file_logger.propagate = False

    if file_logger.handlers:
        return

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file_path = log_path / run_id / "webgym-rl.log"
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )

    file_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    file_logger.addHandler(file_handler)


runtime_logger = _setup_runtime_logger()
file_logger = logging.getLogger()


def setup_logging(
    log_path: Path,
) -> None:
    _setup_file_logger(log_path=log_path)
