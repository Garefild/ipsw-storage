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
    assert not (tmp_path / ("file.ipsw" + download.PARTIAL_SUFFIX)).exists()


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


class InterruptingResponse:
    headers = {"content-length": "6"}

    def __init__(self, exc: BaseException) -> None:
        self.exc = exc

    def __enter__(self) -> InterruptingResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int):
        yield b"abc"
        raise self.exc


def test_download_file_deletes_partial_on_keyboard_interrupt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        download.requests,
        "get",
        lambda url, stream, timeout: InterruptingResponse(KeyboardInterrupt()),
    )

    with pytest.raises(KeyboardInterrupt):
        download.download_file("https://example.com/file.ipsw", tmp_path)

    assert not (tmp_path / "file.ipsw").exists()
    assert not (tmp_path / ("file.ipsw" + download.PARTIAL_SUFFIX)).exists()


def test_download_file_deletes_partial_on_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        download.requests,
        "get",
        lambda url, stream, timeout: InterruptingResponse(
            ConnectionError("network gone")
        ),
    )

    with pytest.raises(ConnectionError):
        download.download_file("https://example.com/file.ipsw", tmp_path)

    assert not (tmp_path / "file.ipsw").exists()
    assert not (tmp_path / ("file.ipsw" + download.PARTIAL_SUFFIX)).exists()


def test_download_file_does_not_overwrite_existing_target_on_interrupt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = tmp_path / "file.ipsw"
    existing.write_bytes(b"original")

    monkeypatch.setattr(
        download.requests,
        "get",
        lambda url, stream, timeout: InterruptingResponse(KeyboardInterrupt()),
    )

    with pytest.raises(KeyboardInterrupt):
        download.download_file("https://example.com/file.ipsw", tmp_path)

    assert existing.read_bytes() == b"original"
    assert not (tmp_path / ("file.ipsw" + download.PARTIAL_SUFFIX)).exists()
