"""Utilities for listing and downloading Apple IPSW firmware."""

from .api import AGENTS, Firmware, FirmwareSource, appledb, fetch_ipsws, ipsw_me
from .download import DownloadProgress, download_file, filename_from_url

try:
    from ._version import __version__, __version_tuple__
except ImportError:
    from importlib.metadata import PackageNotFoundError, version

    try:
        __version__ = version("ipsw-storage")
    except PackageNotFoundError:
        __version__ = "0.0.0+unknown"
    __version_tuple__ = tuple(__version__.split("."))

__all__ = [
    "AGENTS",
    "DownloadProgress",
    "Firmware",
    "FirmwareSource",
    "__version__",
    "__version_tuple__",
    "appledb",
    "download_file",
    "fetch_ipsws",
    "filename_from_url",
    "ipsw_me",
]
