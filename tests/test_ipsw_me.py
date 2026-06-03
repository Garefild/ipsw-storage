from __future__ import annotations

import pytest
import requests

from ipsw_storage.api import ipsw_me


class FakeResponse:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            error = requests.HTTPError(f"{self.status_code} error")
            error.response = self
            raise error
        return None

    def json(self) -> object:
        return self.payload


class FakeSession:
    def __init__(self, responses: dict[str, object]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    def __enter__(self) -> FakeSession:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def get(self, url: str, timeout: int) -> FakeResponse:
        self.urls.append(url)
        response = self.responses[url]
        if isinstance(response, FakeResponse):
            return response
        return FakeResponse(response)


def test_ipsw_me_agent_name_is_ipsw() -> None:
    assert ipsw_me.NAME == "ipsw"


def test_firmwares_for_device_normalizes_records() -> None:
    session = FakeSession(
        {
            "https://api.ipsw.me/v4/device/iPhone16,2?type=ipsw": {
                "firmwares": [
                    {
                        "version": "18.0",
                        "buildid": "22A3354",
                        "signed": True,
                        "filesize": 123,
                        "url": "https://example.com/file.ipsw",
                    },
                    {"version": "17.0"},
                ]
            }
        }
    )

    assert ipsw_me._firmwares_for_device(session, "iPhone16,2") == [
        {
            "device": "iPhone16,2",
            "version": "18.0",
            "buildid": "22A3354",
            "signed": True,
            "filesize": 123,
            "url": "https://example.com/file.ipsw",
        }
    ]


def test_fetch_ipsws_treats_device_404_as_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession(
        {
            "https://api.ipsw.me/v4/device/iPhone99,11?type=ipsw": FakeResponse(
                {},
                status_code=404,
            )
        }
    )
    monkeypatch.setattr(ipsw_me.requests, "Session", lambda: session)

    assert ipsw_me.fetch_ipsws(device="iPhone99,11") == []


def test_fetch_ipsws_rejects_invalid_worker_count() -> None:
    with pytest.raises(ValueError, match="max_workers"):
        ipsw_me.fetch_ipsws(max_workers=0)


def test_fetch_ipsws_filters_signed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_for_device(
        session: requests.Session,
        identifier: str,
    ) -> list[ipsw_me.Firmware]:
        return [
            {
                "device": identifier,
                "version": "18.0",
                "buildid": "B",
                "signed": False,
                "filesize": None,
                "url": "https://example.com/b.ipsw",
            },
            {
                "device": identifier,
                "version": "17.0",
                "buildid": "A",
                "signed": True,
                "filesize": None,
                "url": "https://example.com/a.ipsw",
            },
        ]

    monkeypatch.setattr(ipsw_me, "_firmwares_for_device", fake_for_device)

    assert ipsw_me.fetch_ipsws(device="iPhone16,2", signed_only=True) == [
        {
            "device": "iPhone16,2",
            "version": "17.0",
            "buildid": "A",
            "signed": True,
            "filesize": None,
            "url": "https://example.com/a.ipsw",
        }
    ]
