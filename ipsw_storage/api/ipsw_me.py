"""ipsw.me API agent."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests

from .types import Firmware

NAME = "ipsw"
API_URL = "https://api.ipsw.me/v4/devices"
DEVICE_URL = "https://api.ipsw.me/v4/device/{identifier}?type=ipsw"
REQUEST_TIMEOUT = 30
DEFAULT_MAX_WORKERS = 8


def _get_json(session: requests.Session, url: str) -> Any:
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def _firmwares_for_device(
    session: requests.Session,
    identifier: str,
) -> list[Firmware]:
    payload = _get_json(session, DEVICE_URL.format(identifier=identifier))
    results: list[Firmware] = []

    for fw in payload.get("firmwares", []):
        url = fw.get("url")
        if not url:
            continue

        results.append(
            {
                "device": identifier,
                "version": fw.get("version", ""),
                "buildid": fw.get("buildid", ""),
                "signed": bool(fw.get("signed", False)),
                "filesize": fw.get("filesize"),
                "url": url,
            }
        )

    return results


def _firmwares_for_device_identifier(identifier: str) -> list[Firmware]:
    with requests.Session() as session:
        return _firmwares_for_device(session, identifier)


def fetch_ipsws(
    device: str | None = None,
    *,
    signed_only: bool = False,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> list[Firmware]:
    """Fetch downloadable IPSW records from the ipsw.me API."""
    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")

    with requests.Session() as session:
        if device:
            try:
                results = _firmwares_for_device(session, device)
            except requests.HTTPError as exc:
                if exc.response is None or exc.response.status_code != 404:
                    raise
                results = []
        else:
            devices = _get_json(session, API_URL)
            identifiers = [
                item["identifier"]
                for item in devices
                if isinstance(item, dict) and item.get("identifier")
            ]
            results = []

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(
                        _firmwares_for_device_identifier,
                        identifier,
                    ): identifier
                    for identifier in identifiers
                }

                for future in as_completed(futures):
                    try:
                        results.extend(future.result())
                    except requests.RequestException:
                        continue

    if signed_only:
        results = [item for item in results if item["signed"]]

    return results
