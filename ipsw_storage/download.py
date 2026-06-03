from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from time import monotonic
from urllib.parse import unquote, urlparse

import requests

CHUNK_SIZE = 1024 * 1024
REQUEST_TIMEOUT = 60
ProgressCallback = Callable[["DownloadProgress"], None]


@dataclass(frozen=True)
class DownloadProgress:
    downloaded: int
    total: int | None
    elapsed: float

    @property
    def speed(self) -> float:
        if self.elapsed <= 0:
            return 0.0
        return self.downloaded / self.elapsed

    @property
    def percent(self) -> float | None:
        if not self.total:
            return None
        return min((self.downloaded / self.total) * 100, 100.0)

    @property
    def eta(self) -> float | None:
        if not self.total or self.speed <= 0:
            return None

        remaining = max(self.total - self.downloaded, 0)
        return remaining / self.speed


def filename_from_url(url: str) -> str:
    path = urlparse(url).path
    if not path or path.endswith("/"):
        raise ValueError(f"URL does not contain a filename: {url}")

    filename = Path(unquote(path)).name
    if not filename:
        raise ValueError(f"URL does not contain a filename: {url}")
    return filename


def _content_length(response: requests.Response) -> int | None:
    value = response.headers.get("content-length")
    if not value:
        return None

    try:
        return int(value)
    except ValueError:
        return None


def download_file(
    url: str,
    output_dir: str | PathLike[str],
    *,
    progress_callback: ProgressCallback | None = None,
) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    target = output_dir / filename_from_url(url)

    with requests.get(url, stream=True, timeout=REQUEST_TIMEOUT) as response:
        response.raise_for_status()
        total = _content_length(response)
        downloaded = 0
        started_at = monotonic()

        with target.open("wb") as fp:
            for chunk in response.iter_content(CHUNK_SIZE):
                if chunk:
                    fp.write(chunk)
                    downloaded += len(chunk)

                    if progress_callback is not None:
                        progress_callback(
                            DownloadProgress(
                                downloaded=downloaded,
                                total=total,
                                elapsed=monotonic() - started_at,
                            )
                        )

    return target
