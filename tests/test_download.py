from __future__ import annotations

from pathlib import Path

import pytest

from ipsw_storage import download


class FakeStreamingResponse:
    headers = {"content-length": "6"}

    def __enter__(self) -> FakeStreamingResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int) -> list[bytes]:
        assert chunk_size == download.CHUNK_SIZE
        return [b"abc", b"", b"def"]


def test_filename_from_url_decodes_path_and_ignores_query() -> None:
    assert (
        download.filename_from_url("https://example.com/path/My%20File.ipsw?token=abc")
        == "My File.ipsw"
    )


def test_filename_from_url_requires_filename() -> None:
    with pytest.raises(ValueError, match="filename"):
        download.filename_from_url("https://example.com/path/")


def test_download_file_streams_to_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, bool, int]] = []

    def fake_get(url: str, stream: bool, timeout: int) -> FakeStreamingResponse:
        calls.append((url, stream, timeout))
        return FakeStreamingResponse()

    monkeypatch.setattr(download.requests, "get", fake_get)

    target = download.download_file("https://example.com/file.ipsw", tmp_path)

    assert target == tmp_path / "file.ipsw"
    assert target.read_bytes() == b"abcdef"
    assert calls == [("https://example.com/file.ipsw", True, download.REQUEST_TIMEOUT)]


def test_download_file_reports_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    progress: list[download.DownloadProgress] = []

    def fake_get(url: str, stream: bool, timeout: int) -> FakeStreamingResponse:
        return FakeStreamingResponse()

    monkeypatch.setattr(download.requests, "get", fake_get)

    download.download_file(
        "https://example.com/file.ipsw",
        tmp_path,
        progress_callback=progress.append,
    )

    assert [item.downloaded for item in progress] == [3, 6]
    assert [item.total for item in progress] == [6, 6]
    assert progress[-1].percent == 100.0
