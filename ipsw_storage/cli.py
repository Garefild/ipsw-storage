from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import click
from tqdm import tqdm

from .api import AGENTS, Firmware, FirmwareSource, appledb, fetch_ipsws
from .download import DownloadProgress, download_file

T = TypeVar("T")

SOURCE_CHOICES = [*AGENTS, "both"]


def format_firmware(item: Firmware) -> str:
    signed = "signed" if item["signed"] else "unsigned"
    return (
        f"{item['device']:20} "
        f"{item['version']:10} "
        f"{item['buildid']:15} "
        f"{signed}"
    )


def _run_fzf(lines: list[str], prompt: str) -> str | None:
    if shutil.which("fzf") is None:
        raise click.ClickException("fzf is required for interactive selection")

    result = subprocess.run(
        ["fzf", f"--prompt={prompt}"],
        input="\n".join(lines),
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        return None

    choice = result.stdout.strip()
    return choice or None


def _fzf_pick(
    items: list[T],
    label: Callable[[T], str],
    prompt: str,
) -> T | None:
    mapping: dict[str, T] = {label(item): item for item in items}
    choice = _run_fzf(list(mapping.keys()), prompt)
    if choice is None:
        return None
    return mapping.get(choice)


def fzf_select(items: list[Firmware]) -> Firmware | None:
    return _fzf_pick(items, format_firmware, " ipsw > ")


def fzf_select_device(devices: list[dict[str, Any]]) -> dict[str, Any] | None:
    return _fzf_pick(devices, appledb.format_device_row, " device > ")


def _echo_json(value: Any) -> None:
    click.echo(json.dumps(value, indent=2, sort_keys=True))


def _missing_firmware_message(device: str | None) -> str:
    base_message = "No downloadable IPSW records matched the requested filters"
    if device is None:
        return base_message

    try:
        record = appledb.fetch_device(device)
    except Exception:
        return base_message

    name = record.get("name") or "Unknown device"
    kind = record.get("type") or "unknown"
    internal = " internal" if record.get("internal") else ""

    return (
        f"{base_message}. AppleDB has {device} as "
        f"{kind}{internal}: {name}, but it does not expose a downloadable IPSW "
        f"for that device."
    )


def _load_devices(
    device: str | None,
    device_type: str | None,
) -> list[dict[str, Any]]:
    return appledb.filter_devices(
        appledb.fetch_devices(),
        identifier=device,
        device_type_filter=device_type,
    )


@click.group()
def cli() -> None:
    """IPSW storage utility."""


@cli.group("appledb")
def appledb_group() -> None:
    """Query AppleDB device and OS metadata."""


@appledb_group.command("device")
@click.argument("identifier")
@click.option("--json-output", is_flag=True, help="Print raw JSON metadata.")
def appledb_device_cmd(identifier: str, json_output: bool) -> None:
    """Show AppleDB metadata for a device identifier."""
    record = appledb.fetch_device(identifier)

    if json_output:
        _echo_json(record)
        return

    click.echo(appledb.format_device_summary(record))


@appledb_group.command("firmware")
@click.argument("os_name")
@click.argument("build")
@click.option("--json-output", is_flag=True, help="Print raw JSON metadata.")
def appledb_firmware_cmd(os_name: str, build: str, json_output: bool) -> None:
    """Show AppleDB metadata for an OS build, for example: iOS 22A3354."""
    record = appledb.fetch_os_build(os_name, build)

    if json_output:
        _echo_json(record)
        return

    click.echo(appledb.format_os_build_summary(record))


@cli.command("devices")
@click.option("--device", help="Filter by device identifier, for example iPhone99,11.")
@click.option("--type", "device_type", help="Filter by AppleDB device type.")
@click.option("--json-output", is_flag=True, help="Print raw JSON metadata.")
@click.option(
    "--interactive",
    "-i",
    is_flag=True,
    help="Pick a device interactively with fzf and print its summary.",
)
def list_devices(
    device: str | None,
    device_type: str | None,
    json_output: bool,
    interactive: bool,
) -> None:
    """List AppleDB device records, including simulators and internal devices."""
    devices = _load_devices(device, device_type)

    if interactive:
        selected = fzf_select_device(devices)
        if selected is None:
            raise click.Abort()
        click.echo(appledb.format_device_summary(selected))
        return

    if json_output:
        _echo_json(devices)
        return

    for item in devices:
        click.echo(appledb.format_device_row(item))


@cli.command("list")
@click.option("--device", help="Filter by device identifier, for example iPhone16,2.")
@click.option(
    "--signed-only",
    is_flag=True,
    help="Only include firmware that is still signed.",
)
@click.option("--json-output", is_flag=True, help="Print raw JSON records.")
@click.option(
    "--source",
    type=click.Choice(SOURCE_CHOICES),
    default="both",
    show_default=True,
    help="Firmware API source to query.",
)
def list_firmwares(
    device: str | None,
    signed_only: bool,
    json_output: bool,
    source: FirmwareSource,
) -> None:
    """List IPSW firmware records."""
    items = fetch_ipsws(device=device, signed_only=signed_only, source=source)

    if json_output:
        _echo_json(items)
        return

    for item in items:
        click.echo(format_firmware(item))


@cli.command()
@click.argument(
    "directory",
    type=click.Path(file_okay=False, path_type=Path),
)
@click.option("--device", help="Limit interactive selection to one device identifier.")
@click.option(
    "--signed-only",
    is_flag=True,
    help="Only show firmware that is still signed.",
)
@click.option(
    "--source",
    type=click.Choice(SOURCE_CHOICES),
    default="both",
    show_default=True,
    help="Firmware API source to query.",
)
@click.option(
    "--pick-device",
    is_flag=True,
    help="First pick a device from AppleDB via fzf, then pick a firmware.",
)
@click.option(
    "--version",
    "version",
    help="Firmware version (e.g. 26.1). Skips fzf when the match is unique.",
)
@click.option(
    "--build",
    "build",
    help="Firmware build ID (e.g. 23B85). Skips fzf when the match is unique.",
)
def pull(
    directory: Path,
    device: str | None,
    signed_only: bool,
    source: FirmwareSource,
    pick_device: bool,
    version: str | None,
    build: str | None,
) -> None:
    """Select and download an IPSW."""
    if pick_device:
        click.echo("Loading AppleDB devices...")
        selected_device = fzf_select_device(_load_devices(None, None))
        if selected_device is None:
            raise click.Abort()
        identifiers = [
            str(item)
            for item in (selected_device.get("identifier") or [])
        ]
        device = identifiers[0] if identifiers else device

    click.echo("Loading IPSW catalog...")
    items = fetch_ipsws(device=device, signed_only=signed_only, source=source)

    if version:
        items = [item for item in items if item["version"] == version]
    if build:
        items = [item for item in items if item["buildid"] == build]

    if not items:
        raise click.ClickException(_missing_firmware_message(device))

    if len(items) == 1:
        selected = items[0]
    else:
        selected = fzf_select(items)
        if selected is None:
            raise click.Abort()

    click.echo(f"Downloading {selected['device']} {selected['version']}...")

    with tqdm(
        total=selected["filesize"],
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        dynamic_ncols=True,
        desc=f"{selected['device']} {selected['version']}",
        leave=True,
    ) as progress_bar:
        last_downloaded = 0

        def show_progress(progress: DownloadProgress) -> None:
            nonlocal last_downloaded

            if progress_bar.total is None and progress.total is not None:
                progress_bar.reset(total=progress.total)

            progress_bar.update(progress.downloaded - last_downloaded)
            last_downloaded = progress.downloaded

        target = download_file(
            selected["url"],
            directory,
            progress_callback=show_progress,
        )

    click.secho(f"Saved to {target}", fg="green")


if __name__ == "__main__":
    cli()
