from __future__ import annotations

from click.testing import CliRunner

from ipsw_storage import cli as cli_module
from ipsw_storage.api import appledb

FIRMWARE = {
    "device": "iPhone16,2",
    "version": "18.0",
    "buildid": "22A3354",
    "signed": True,
    "filesize": 123,
    "url": "https://example.com/file.ipsw",
}


def test_list_outputs_json(monkeypatch) -> None:
    monkeypatch.setattr(cli_module, "fetch_ipsws", lambda **kwargs: [FIRMWARE])

    result = CliRunner().invoke(cli_module.cli, ["list", "--json-output"])

    assert result.exit_code == 0
    assert '"device": "iPhone16,2"' in result.output


def test_pull_aborts_when_no_records(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli_module, "fetch_ipsws", lambda **kwargs: [])

    result = CliRunner().invoke(cli_module.cli, ["pull", str(tmp_path)])

    assert result.exit_code != 0
    assert "No downloadable IPSW records matched" in result.output


def test_pull_explains_appledb_device_without_downloads(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli_module, "fetch_ipsws", lambda **kwargs: [])
    monkeypatch.setattr(
        appledb,
        "fetch_device",
        lambda identifier: {
            "name": "virtual machine for iPhone Research Environment",
            "identifier": [identifier],
            "type": "Simulator",
            "internal": True,
        },
    )

    result = CliRunner().invoke(
        cli_module.cli,
        ["pull", str(tmp_path), "--device", "iPhone99,11"],
    )

    assert result.exit_code != 0
    assert "AppleDB has iPhone99,11 as Simulator internal" in result.output
    assert "does not expose a downloadable IPSW" in result.output


def test_appledb_device_outputs_summary(monkeypatch) -> None:
    monkeypatch.setattr(
        appledb,
        "fetch_device",
        lambda identifier: {
            "name": "iPhone 15 Pro Max",
            "identifier": [identifier],
        },
    )

    result = CliRunner().invoke(cli_module.cli, ["appledb", "device", "iPhone16,2"])

    assert result.exit_code == 0
    assert "Name: iPhone 15 Pro Max" in result.output
    assert "Identifier: iPhone16,2" in result.output


def test_devices_outputs_appledb_simulator(monkeypatch) -> None:
    monkeypatch.setattr(
        appledb,
        "fetch_devices",
        lambda: [
            {
                "name": "virtual machine for iPhone Research Environment",
                "identifier": ["iPhone99,11"],
                "type": "Simulator",
                "internal": True,
            }
        ],
    )

    result = CliRunner().invoke(
        cli_module.cli,
        ["devices", "--device", "iPhone99,11", "--type", "Simulator"],
    )

    assert result.exit_code == 0
    assert "iPhone99,11" in result.output
    assert "Simulator" in result.output
    assert "internal" in result.output


def test_devices_interactive_uses_fzf_picker(monkeypatch) -> None:
    device_record = {
        "name": "iPhone 15 Pro Max",
        "identifier": ["iPhone16,2"],
        "type": "iPhone",
    }
    monkeypatch.setattr(appledb, "fetch_devices", lambda: [device_record])
    monkeypatch.setattr(
        cli_module,
        "fzf_select_device",
        lambda devices: devices[0],
    )

    result = CliRunner().invoke(cli_module.cli, ["devices", "--interactive"])

    assert result.exit_code == 0
    assert "Name: iPhone 15 Pro Max" in result.output
    assert "Identifier: iPhone16,2" in result.output


def test_pull_with_unique_version_skips_fzf(monkeypatch, tmp_path) -> None:
    record = {
        "device": "iPhone99,11",
        "version": "26.1",
        "buildid": "23B85",
        "signed": False,
        "filesize": None,
        "url": "https://example.com/iPhone99,11.ipsw",
    }
    monkeypatch.setattr(cli_module, "fetch_ipsws", lambda **kwargs: [record])

    def fail_fzf(_items):
        raise AssertionError("fzf should not run for a unique match")

    monkeypatch.setattr(cli_module, "fzf_select", fail_fzf)

    downloads: list[str] = []

    def fake_download(url, output_dir, *, progress_callback=None):
        downloads.append(url)
        return tmp_path / "iPhone99,11.ipsw"

    monkeypatch.setattr(cli_module, "download_file", fake_download)

    result = CliRunner().invoke(
        cli_module.cli,
        [
            "pull",
            str(tmp_path),
            "--device",
            "iPhone99,11",
            "--version",
            "26.1",
        ],
    )

    assert result.exit_code == 0, result.output
    assert downloads == ["https://example.com/iPhone99,11.ipsw"]


def test_pull_with_version_falls_through_to_fzf_when_ambiguous(
    monkeypatch, tmp_path
) -> None:
    records = [
        {
            "device": "iPhone99,11",
            "version": "26.3",
            "buildid": "23D128",
            "signed": False,
            "filesize": None,
            "url": "https://example.com/a.ipsw",
        },
        {
            "device": "iPhone99,11",
            "version": "26.3",
            "buildid": "23D129",
            "signed": False,
            "filesize": None,
            "url": "https://example.com/b.ipsw",
        },
    ]
    monkeypatch.setattr(cli_module, "fetch_ipsws", lambda **kwargs: records)

    selected_passed: list[list[dict]] = []

    def fake_fzf(items):
        selected_passed.append(items)
        return items[1]

    monkeypatch.setattr(cli_module, "fzf_select", fake_fzf)
    monkeypatch.setattr(
        cli_module,
        "download_file",
        lambda url, output_dir, *, progress_callback=None: tmp_path / "x.ipsw",
    )

    result = CliRunner().invoke(
        cli_module.cli,
        [
            "pull",
            str(tmp_path),
            "--device",
            "iPhone99,11",
            "--version",
            "26.3",
        ],
    )

    assert result.exit_code == 0, result.output
    assert len(selected_passed) == 1
    assert {item["buildid"] for item in selected_passed[0]} == {"23D128", "23D129"}


def test_pull_with_build_pins_to_one_record(monkeypatch, tmp_path) -> None:
    records = [
        {
            "device": "iPhone99,11",
            "version": "26.3",
            "buildid": "23D128",
            "signed": False,
            "filesize": None,
            "url": "https://example.com/a.ipsw",
        },
        {
            "device": "iPhone99,11",
            "version": "26.3",
            "buildid": "23D129",
            "signed": False,
            "filesize": None,
            "url": "https://example.com/b.ipsw",
        },
    ]
    monkeypatch.setattr(cli_module, "fetch_ipsws", lambda **kwargs: records)
    monkeypatch.setattr(
        cli_module,
        "fzf_select",
        lambda items: (_ for _ in ()).throw(AssertionError("should not fzf")),
    )

    downloaded: list[str] = []
    monkeypatch.setattr(
        cli_module,
        "download_file",
        lambda url, output_dir, *, progress_callback=None: (
            downloaded.append(url) or tmp_path / "b.ipsw"
        ),
    )

    result = CliRunner().invoke(
        cli_module.cli,
        [
            "pull",
            str(tmp_path),
            "--device",
            "iPhone99,11",
            "--build",
            "23D129",
        ],
    )

    assert result.exit_code == 0, result.output
    assert downloaded == ["https://example.com/b.ipsw"]


def test_devices_interactive_aborts_when_no_selection(monkeypatch) -> None:
    monkeypatch.setattr(
        appledb,
        "fetch_devices",
        lambda: [
            {
                "name": "iPhone 15 Pro Max",
                "identifier": ["iPhone16,2"],
                "type": "iPhone",
            }
        ],
    )
    monkeypatch.setattr(cli_module, "fzf_select_device", lambda devices: None)

    result = CliRunner().invoke(cli_module.cli, ["devices", "--interactive"])

    assert result.exit_code != 0
