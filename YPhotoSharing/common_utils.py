"""
Common utility functions shared between client and server components.
"""

import gzip
import json
import logging
import os
import shutil
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


def validate_config_directory(config_path: str, required_files: list = None) -> Path:
    """
    Validate that the configuration directory exists and contains required files.

    Args:
        config_path: Path string to configuration directory
        required_files: List of required file names within the directory

    Returns:
        Path object for the validated configuration directory

    Raises:
        SystemExit: If directory or required files are missing
    """
    config_dir = Path(config_path).expanduser().resolve()

    if not config_dir.exists():
        print(f"❌ Error: Configuration directory does not exist: '{config_dir}'")
        sys.exit(1)

    if not config_dir.is_dir():
        print(f"❌ Error: Configuration path is not a directory: '{config_dir}'")
        sys.exit(1)

    for fname in required_files or []:
        fpath = config_dir / fname
        if not fpath.exists():
            print(f"❌ Error: Required configuration file not found: '{fpath}'")
            print(f"   Expected in directory: '{config_dir}'")
            sys.exit(1)

    return config_dir


def load_json_config(config_file: Path) -> dict:
    """
    Load and parse a JSON configuration file.

    Args:
        config_file: Path to the JSON configuration file

    Returns:
        Parsed configuration dictionary

    Raises:
        SystemExit: On parse errors
    """
    try:
        with open(config_file, "r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in '{config_file}': {e}")
        sys.exit(1)
    except OSError as e:
        print(f"❌ Error: Cannot read configuration file '{config_file}': {e}")
        sys.exit(1)


def _compress_rotated_log(source, dest):
    with open(source, "rb") as f_in:
        with gzip.open(dest, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    os.remove(source)


class _JsonFormatter(logging.Formatter):
    def __init__(self, *, indent: Optional[int] = None, include_module: bool = True):
        super().__init__()
        self._indent = indent
        self._include_module = include_module

    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if self._include_module:
            log_data.update(
                {
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno,
                }
            )
        if hasattr(record, "execution_time"):
            log_data["execution_time_ms"] = record.execution_time
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)
        return json.dumps(log_data, indent=self._indent)


def build_structured_file_logger(
    logger_name: str,
    log_file: Path,
    *,
    level: int = logging.INFO,
    backup_count: int = 5,
    max_bytes: int = 10 * 1024 * 1024,
    indent: Optional[int] = None,
    include_module: bool = True,
    propagate: bool = False,
) -> logging.Logger:
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.propagate = propagate
    if logger.handlers:
        logger.handlers.clear()

    log_file.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
    handler.rotator = _compress_rotated_log
    handler.namer = lambda name: name + ".gz"
    handler.setFormatter(_JsonFormatter(indent=indent, include_module=include_module))
    logger.addHandler(handler)
    return logger


def build_json_line_file_logger(
    logger_name: str,
    log_file: Path,
    *,
    level: int = logging.INFO,
    backup_count: int = 5,
    max_bytes: int = 10 * 1024 * 1024,
    propagate: bool = False,
) -> logging.Logger:
    """Create a rotating file logger that writes one preformatted JSON line per record."""
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.propagate = propagate
    if logger.handlers:
        logger.handlers.clear()

    log_file.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
    handler.rotator = _compress_rotated_log
    handler.namer = lambda name: name + ".gz"
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    return logger


def setup_logging(
    config_dir: Path,
    component_name: str,
    logging_config_or_enable_console=True,
    instance_name: Optional[str] = None,
    enable_console: Optional[bool] = None,
):
    """
    Configure execution logging in the same shape used by YSimulator.

    The helper writes JSON execution logs to ``config_dir/logs`` using
    gzip-compressed rotation, and returns a component-specific logger that
    propagates into the configured root handlers.
    """
    if isinstance(logging_config_or_enable_console, dict):
        logging_config = logging_config_or_enable_console
        enable_console_flag = logging_config.get("enable_console_log", True)
        if component_name.lower() == "server":
            enable_execution_log = logging_config.get("enable_server_log", True)
        else:
            enable_execution_log = logging_config.get("enable_execution_log", True)
    else:
        logging_config = {}
        enable_console_flag = bool(logging_config_or_enable_console)
        enable_execution_log = True

    if enable_console is not None:
        enable_console_flag = enable_console

    log_dir = config_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    component_key = component_name.lower()
    resolved_name = instance_name or component_key

    if component_key == "client":
        log_file = log_dir / f"{resolved_name}_execution.log"
    elif component_key == "server":
        log_file = log_dir / f"{resolved_name}_server.log"
    else:
        log_file = log_dir / f"{resolved_name}.log"

    if enable_execution_log:
        file_handler = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5)
        file_handler.rotator = _compress_rotated_log
        file_handler.namer = lambda name: name + ".gz"
        file_handler.setFormatter(_JsonFormatter())
        root_logger.addHandler(file_handler)
        root_logger.info(
            "Execution logging enabled",
            extra={
                "extra_data": {
                    "component": component_key,
                    "instance_name": resolved_name,
                    "log_file": str(log_file),
                }
            },
        )

    enable_actor_log = logging_config.get("enable_actor_log", True)
    if enable_actor_log:
        if component_key == "client":
            actor_log_file = log_dir / f"{resolved_name}_actor.log"
        elif component_key == "server":
            actor_log_file = log_dir / f"{resolved_name}_actor.log"
        else:
            actor_log_file = log_dir / f"{resolved_name}_actor.log"

        actor_handler = RotatingFileHandler(actor_log_file, maxBytes=10 * 1024 * 1024, backupCount=5)
        actor_handler.rotator = _compress_rotated_log
        actor_handler.namer = lambda name: name + ".gz"
        actor_handler.setFormatter(_JsonFormatter())
        root_logger.addHandler(actor_handler)
        root_logger.info(
            "Actor logging enabled",
            extra={
                "extra_data": {
                    "component": component_key,
                    "instance_name": resolved_name,
                    "log_file": str(actor_log_file),
                }
            },
        )

    if enable_console_flag:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        root_logger.addHandler(console_handler)

    return logging.getLogger(f"YPhotoSharing.{component_name.capitalize()}.{resolved_name}")
