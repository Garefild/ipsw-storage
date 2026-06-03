from __future__ import annotations

from typing import Any

from ipsw_storage.api import appledb


class FakeResponse:
    def __init__(self, payload: Any) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self.payload


class FakeSession:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def __enter__(self) -> FakeSession:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def get(self, url: str, timeout: int) -> FakeResponse:
        self.urls.append(url)
        return FakeResponse(
            {
                "name": "iPhone 15 Pro Max",
                "identifier": ["iPhone16,2"],
                "model": ["A2849"],
                "released": "2023-09-22",
                "soc": "A17 Pro",
                "arch": "arm64e",
            }
        )


def test_appledb_agent_name_is_appledb() -> None:
    assert appledb.NAME == "appledb"


def test_fetch_device_uses_encoded_identifier(monkeypatch) -> None:
    session = FakeSession()
    monkeypatch.setattr(appledb.requests, "Session", lambda: session)

    assert appledb.fetch_device("iPhone16,2")["name"] == "iPhone 15 Pro Max"
    assert session.urls == ["https://api.appledb.dev/device/iPhone16%2C2.json"]


def test_fetch_os_build_uses_encoded_key(monkeypatch) -> None:
    session = FakeSession()
    monkeypatch.setattr(appledb.requests, "Session", lambda: session)

    appledb.fetch_os_build("iOS", "22A3354")

    assert session.urls == ["https://api.appledb.dev/ios/iOS%3B22A3354.json"]


def test_firmwares_from_build_extracts_preferred_ipsw_source() -> None:
    records = appledb._firmwares_from_build(
        {
            "version": "26.5",
            "build": "23F77",
            "signed": ["iPhone16,2"],
            "sources": [
                {
                    "type": "ipsw",
                    "deviceMap": ["iPhone16,2"],
                    "size": 123,
                    "links": [
                        {
                            "url": "http://example.com/iPhone16,2.ipsw",
                            "preferred": False,
                            "active": True,
                        },
                        {
                            "url": "https://example.com/iPhone16,2.ipsw",
                            "preferred": True,
                            "active": True,
                        },
                    ],
                }
            ],
        }
    )

    assert records == [
        {
            "device": "iPhone16,2",
            "version": "26.5",
            "buildid": "23F77",
            "signed": True,
            "filesize": 123,
            "url": "https://example.com/iPhone16,2.ipsw",
        }
    ]


def test_fetch_ipsws_filters_device_and_signed(monkeypatch) -> None:
    monkeypatch.setattr(
        appledb,
        "fetch_os_builds",
        lambda: [
            {
                "version": "26.5",
                "build": "23F77",
                "signed": ["iPhone16,2"],
                "sources": [
                    {
                        "type": "ipsw",
                        "deviceMap": ["iPhone16,2", "iPhone99,11"],
                        "size": 123,
                        "links": [
                            {
                                "url": "https://example.com/shared.ipsw",
                                "preferred": True,
                                "active": True,
                            }
                        ],
                    }
                ],
            }
        ],
    )

    assert appledb.fetch_ipsws(device="iPhone16,2", signed_only=True) == [
        {
            "device": "iPhone16,2",
            "version": "26.5",
            "buildid": "23F77",
            "signed": True,
            "filesize": 123,
            "url": "https://example.com/shared.ipsw",
        }
    ]


def test_firmwares_from_build_keeps_extensionless_cdn_links() -> None:
    records = appledb._firmwares_from_build(
        {
            "version": "26.1",
            "build": "23B85",
            "signed": ["iPhone99,11"],
            "sources": [
                {
                    "type": "ipsw",
                    "deviceMap": ["iPhone99,11"],
                    "size": 935422803,
                    "links": [
                        {
                            "url": "https://updates.cdn-apple.com/private-cloud-compute/399b664d",
                            "preferred": True,
                            "active": True,
                        },
                        {
                            "url": "http://updates-http.cdn-apple.com/private-cloud-compute/399b664d",
                            "preferred": False,
                            "active": True,
                        },
                    ],
                }
            ],
        }
    )

    assert records == [
        {
            "device": "iPhone99,11",
            "version": "26.1",
            "buildid": "23B85",
            "signed": True,
            "filesize": 935422803,
            "url": "https://updates.cdn-apple.com/private-cloud-compute/399b664d",
        }
    ]


def test_filter_devices_finds_simulator_identifier() -> None:
    devices = [
        {
            "name": "virtual machine for iPhone Research Environment",
            "identifier": ["iPhone99,11"],
            "type": "Simulator",
            "internal": True,
        },
        {
            "name": "iPhone 15 Pro Max",
            "identifier": ["iPhone16,2"],
            "type": "iPhone",
        },
    ]

    assert appledb.filter_devices(
        devices,
        identifier="iPhone99,11",
        device_type_filter="Simulator",
    ) == [devices[0]]


def test_format_device_row_includes_type_identifier_and_internal_marker() -> None:
    assert appledb.format_device_row(
        {
            "name": "virtual machine for iPhone Research Environment",
            "identifier": ["iPhone99,11"],
            "type": "Simulator",
            "internal": True,
        }
    ) == (
        "iPhone99,11              Simulator    "
        "virtual machine for iPhone Research Environment internal"
    )


def test_format_device_summary_handles_common_fields() -> None:
    summary = appledb.format_device_summary(
        {
            "name": "iPhone 15 Pro Max",
            "identifier": ["iPhone16,2"],
            "model": ["A2849", "A3105"],
            "released": "2023-09-22",
            "soc": "A17 Pro",
            "arch": "arm64e",
        }
    )

    assert "Name: iPhone 15 Pro Max" in summary
    assert "Identifier: iPhone16,2" in summary
    assert "Type: unknown" in summary
    assert "Model: A2849, A3105" in summary


def test_format_os_build_summary_handles_signed_devices() -> None:
    summary = appledb.format_os_build_summary(
        {
            "osStr": "iOS",
            "version": "18.0",
            "build": "22A3354",
            "released": "2024-09-16",
            "signed": ["iPhone16,2"],
        }
    )

    assert "OS: iOS" in summary
    assert "Version: 18.0" in summary
    assert "Signing: signed for 1 device(s)" in summary
