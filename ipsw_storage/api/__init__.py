"""IPSW catalog orchestrator.

Each API agent (`ipsw_me`, `appledb`) follows the same contract:

    NAME: str
    def fetch_ipsws(device: str | None = None, *, signed_only: bool = False)
        -> list[Firmware]

`fetch_ipsws` here picks one or more agents by `source` and merges them.
"""
from __future__ import annotations

from . import appledb, ipsw_me
from .types import Firmware, FirmwareSource

AGENTS = {ipsw_me.NAME: ipsw_me, appledb.NAME: appledb}


def fetch_ipsws(
    device: str | None = None,
    *,
    signed_only: bool = False,
    source: FirmwareSource = "both",
) -> list[Firmware]:
    """Fetch IPSW records from the selected source(s)."""
    if source == "both":
        agents = list(AGENTS.values())
    elif source in AGENTS:
        agents = [AGENTS[source]]
    else:
        valid = ", ".join([*AGENTS, "both"])
        raise ValueError(f"source must be one of: {valid}")

    results: list[Firmware] = []
    for agent in agents:
        results.extend(agent.fetch_ipsws(device=device, signed_only=signed_only))

    return _sort_firmwares(_deduplicate_firmwares(results))


def _deduplicate_firmwares(items: list[Firmware]) -> list[Firmware]:
    seen: set[tuple[str, str, str]] = set()
    results: list[Firmware] = []

    for item in items:
        key = (item["device"], item["buildid"], item["url"])
        if key in seen:
            continue
        seen.add(key)
        results.append(item)

    return results


def _sort_firmwares(results: list[Firmware]) -> list[Firmware]:
    return sorted(
        results,
        key=lambda item: (item["device"], item["version"], item["buildid"]),
    )


__all__ = [
    "AGENTS",
    "Firmware",
    "FirmwareSource",
    "appledb",
    "fetch_ipsws",
    "ipsw_me",
]
