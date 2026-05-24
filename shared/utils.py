"""
utils.py — Data loading and logging helpers for the PoC Platform.

Provides a consistent interface for accessing mock data files and
formatting output values. All path resolution is relative to this
file's location so the helpers work regardless of the working directory
the Streamlit app is launched from.

Usage:
    from shared.utils import load_document, load_csv, load_json, get_logger

    logger = get_logger("my_app")
    df = load_csv("sales_transactions_2023_2024.csv")
    doc = load_document("contract_sample_nda.txt")
    data = load_json("quarterly_kpis_2024.json")
"""

import json
import logging
import os
import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_SHARED_DIR = Path(__file__).parent
_MOCK_DATA_DIR = _SHARED_DIR / "mock_data"
_DOCUMENTS_DIR = _MOCK_DATA_DIR / "documents"
_DATASETS_DIR = _MOCK_DATA_DIR / "datasets"
_BI_DATA_DIR = _MOCK_DATA_DIR / "bi_data"

_LOG_DIR = Path("/var/log/streamlit")


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    """
    Return a configured Python logger that writes to a rotating file.

    The log file is written to ``/var/log/streamlit/{name}.log``. If that
    directory cannot be created (e.g. permission denied in local dev), the
    logger falls back to stdout so the app never crashes due to logging.

    Args:
        name: Logical name for the logger, typically the app or module name.

    Returns:
        A `logging.Logger` instance with at least one handler attached.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        # Already configured — return early to avoid duplicate handlers
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(_LOG_DIR / f"{name}.log")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except (PermissionError, OSError):
        # Fall back to stdout when the log directory isn't writable
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger


# ---------------------------------------------------------------------------
# Document helpers
# ---------------------------------------------------------------------------

def load_document(filename: str) -> str:
    """
    Read a plain-text document from the mock_data/documents directory.

    Args:
        filename: Filename including extension, e.g. ``"contract_sample_nda.txt"``.

    Returns:
        The full file contents as a UTF-8 string.

    Raises:
        FileNotFoundError: If the file does not exist in the documents folder.
    """
    path = _DOCUMENTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {path}")
    return path.read_text(encoding="utf-8")


def list_documents() -> list[str]:
    """
    Return a sorted list of .txt filenames in the documents directory.

    Returns:
        List of filenames (not full paths), e.g. ``["contract_sample_nda.txt", ...]``.
    """
    if not _DOCUMENTS_DIR.exists():
        return []
    return sorted(p.name for p in _DOCUMENTS_DIR.glob("*.txt"))


# ---------------------------------------------------------------------------
# Dataset helpers
# ---------------------------------------------------------------------------

def load_csv(filename: str, subfolder: str = "datasets") -> pd.DataFrame:
    """
    Load a CSV file from mock_data into a pandas DataFrame.

    Args:
        filename:  Filename including extension, e.g. ``"sales_transactions_2023_2024.csv"``.
        subfolder: Sub-directory under mock_data. Defaults to ``"datasets"``.

    Returns:
        A pandas DataFrame containing the CSV data.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    path = _MOCK_DATA_DIR / subfolder / filename
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    return pd.read_csv(path)


def list_datasets() -> list[str]:
    """
    Return a sorted list of .csv filenames in the datasets directory.

    Returns:
        List of filenames (not full paths).
    """
    if not _DATASETS_DIR.exists():
        return []
    return sorted(p.name for p in _DATASETS_DIR.glob("*.csv"))


# ---------------------------------------------------------------------------
# JSON / BI data helpers
# ---------------------------------------------------------------------------

def load_json(filename: str, subfolder: str = "bi_data") -> dict:
    """
    Load a JSON file from mock_data into a Python dictionary.

    Args:
        filename:  Filename including extension, e.g. ``"quarterly_kpis_2024.json"``.
        subfolder: Sub-directory under mock_data. Defaults to ``"bi_data"``.

    Returns:
        Parsed JSON contents as a Python dict (or list, if the root is an array).

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    path = _MOCK_DATA_DIR / subfolder / filename
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_currency(amount: float) -> str:
    """
    Format a numeric value as a USD currency string.

    Args:
        amount: Numeric dollar amount, e.g. ``1234567.89``.

    Returns:
        Formatted string, e.g. ``"$1,234,567.89"``.
    """
    return f"${amount:,.2f}"


def format_pct(value: float) -> str:
    """
    Format a decimal fraction as a percentage string.

    Args:
        value: Float between 0 and 1, e.g. ``0.975``.

    Returns:
        Formatted string, e.g. ``"97.5%"``.
    """
    return f"{value * 100:.1f}%"
