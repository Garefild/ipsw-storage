"""AppleDB API agent."""
from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlparse

import requests

from .types import Firmware

NAME = "appledb"
APPLEDB_API_URL = "https://api.appledb.dev"
REQUEST_TIMEOUT = 30


def _get_json(session: requests.Session, path: str) -> Any:
    response = session.get(f"{APPLEDB_API_URL}{path}", timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def fetch_device(identifier: str) -> dict[str, Any]:
    """Fetch AppleDB metadata for one device identifier."""
    encoded = quote(identifier, safe="")
    with requests.Session() as session:
        return _get_json(session, f"/device/{encoded}.json")


def fetch_devices() -> list[dict[str, Any]]:
    """Fetch AppleDB metadata for all devices."""
    with requests.Session() as session:
        devices = _get_json(session, "/device/main.json")

    if not isinstance(devices, list):
        raise ValueError("AppleDB device response must be a list")

    return devices


def fetch_os_build(os_name: str, build: str) -> dict[str, Any]:
    """Fetch AppleDB metadata for one OS build."""
    key = quote(f"{os_name};{build}", safe="")
    with requests.Session() as session:
        return _get_json(session, f"/ios/{key}.json")


def fetch_os_builds() -> list[dict[str, Any]]:
    """Fetch AppleDB metadata for all OS builds."""
    with requests.Session() as session:
        builds = _get_json(session, "/ios/main.json")

    if not isinstance(builds, list):
        raise ValueError("AppleDB OS response must be a list")

    return builds


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def device_identifiers(device: dict[str, Any]) -> list[str]:
    return [str(item) for item in _as_list(device.get("identifier"))]


def device_models(device: dict[str, Any]) -> list[str]:
    return [str(item) for item in _as_list(device.get("model"))]


def device_type(device: dict[str, Any]) -> str:
    return str(device.get("type") or "unknown")


def filter_devices(
    devices: list[dict[str, Any]],
    *,
    identifier: str | None = None,
    device_type_filter: str | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    for device in devices:
        identifiers = device_identifiers(device)
        if identifier is not None and identifier not in identifiers:
            continue
        if device_type_filter is not None and device_type(device) != device_type_filter:
            continue
        results.append(device)

    return sorted(
        results,
        key=lambda item: (
            device_type(item),
            device_identifiers(item)[0] if device_identifiers(item) else "",
        ),
    )


def format_device_row(device: dict[str, Any]) -> str:
    identifiers = ", ".join(device_identifiers(device)) or "unknown"
    name = str(device.get("name") or "Unknown device")
    internal = " internal" if device.get("internal") else ""

    return f"{identifiers:24} {device_type(device):12} {name}{internal}"


def format_device_summary(device: dict[str, Any]) -> str:
    name = str(device.get("name") or "Unknown device")
    identifiers = ", ".join(device_identifiers(device)) or "unknown"
    models = ", ".join(device_models(device)) or "unknown"
    released = str(device.get("released") or "unknown")
    soc = str(device.get("soc") or "unknown")
    arch = str(device.get("arch") or "unknown")
    kind = device_type(device)
    internal = "yes" if device.get("internal") else "no"

    return "\n".join(
        [
            f"Name: {name}",
            f"Identifier: {identifiers}",
            f"Type: {kind}",
            f"Internal: {internal}",
            f"Model: {models}",
            f"Released: {released}",
            f"SoC: {soc}",
            f"Arch: {arch}",
        ]
    )


def format_os_build_summary(build: dict[str, Any]) -> str:
    name = str(build.get("osStr") or build.get("name") or "Unknown OS")
    version = str(build.get("version") or "unknown")
    build_id = str(build.get("build") or build.get("buildId") or "unknown")
    released = str(build.get("released") or "unknown")
    signed = build.get("signed")

    if signed is True:
        signed_text = "signed"
    elif signed:
        signed_text = f"signed for {len(_as_list(signed))} device(s)"
    else:
        signed_text = "not signed"

    return "\n".join(
        [
            f"OS: {name}",
            f"Version: {version}",
            f"Build: {build_id}",
            f"Released: {released}",
            f"Signing: {signed_text}",
        ]
    )


def _source_devices(source: dict[str, Any], build: dict[str, Any]) -> list[str]:
    devices = _as_list(source.get("deviceMap")) or _as_list(build.get("deviceMap"))
    return [str(item) for item in devices]


def _source_url(source: dict[str, Any]) -> str | None:
    links = [
        link
        for link in _as_list(source.get("links"))
        if isinstance(link, dict) and link.get("url")
    ]
    if not links:
        return None

    preferred_active = [
        link for link in links if link.get("preferred") and link.get("active", True)
    ]
    active = [link for link in links if link.get("active", True)]
    candidates = [*preferred_active, *active, *links]

    # Prefer .ipsw-suffixed URLs when present, but fall back to any candidate:
    # cloudOS (Private Cloud Compute) firmware ships as hash-suffixed CDN paths
    # with no extension.
    for link in candidates:
        url = str(link["url"])
        if urlparse(url).path.lower().endswith(".ipsw"):
            return url

    return str(candidates[0]["url"])


def _is_signed(build: dict[str, Any], identifier: str) -> bool:
    signed = build.get("signed")
    return signed is True or identifier in _as_list(signed)


def _firmwares_from_build(build: dict[str, Any]) -> list[Firmware]:
    results: list[Firmware] = []

    for source in _as_list(build.get("sources")):
        if not isinstance(source, dict) or source.get("type") != "ipsw":
            continue

        url = _source_url(source)
        if not url:
            continue

        for identifier in _source_devices(source, build):
            results.append(
                {
                    "device": identifier,
                    "version": str(build.get("version") or ""),
                    "buildid": str(
                        build.get("build") or build.get("uniqueBuild") or ""
                    ),
                    "signed": _is_signed(build, identifier),
                    "filesize": source.get("size"),
                    "url": url,
                }
            )

    return results


def fetch_ipsws(
    device: str | None = None,
    *,
    signed_only: bool = False,
) -> list[Firmware]:
    """Fetch downloadable IPSW records from AppleDB firmware sources."""
    results: list[Firmware] = []

    for build in fetch_os_builds():
        if not isinstance(build, dict):
            continue

        for firmware in _firmwares_from_build(build):
            if device is not None and firmware["device"] != device:
                continue
            if signed_only and not firmware["signed"]:
                continue
            results.append(firmware)

    return results
