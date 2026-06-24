"""
Common utility functions shared between client and server components.
"""

import json
import sys
from pathlib import Path


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


def setup_logging(config_dir: Path, component_name: str, enable_console: bool = True):
    """
    Configure execution logging equivalently to YSimulator.
    Creates a 'logs' directory inside the config directory and writes execution logs.
    """
    import logging
    import os
    from logging.handlers import RotatingFileHandler

    log_dir = config_dir / "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = log_dir / f"execution_{component_name}.log"

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Clear existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # File Handler
    fh = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Console Handler
    if enable_console:
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    return logging.getLogger(f"YPhotoSharing.{component_name.capitalize()}")
