from __future__ import annotations

from typing import Literal, TypedDict

FirmwareSource = Literal["ipsw", "appledb", "both"]


class Firmware(TypedDict):
    device: str
    version: str
    buildid: str
    signed: bool
    filesize: int | None
    url: str
