from __future__ import annotations

import pytest

from ipsw_storage import api
from ipsw_storage.api import appledb, ipsw_me


def test_fetch_ipsws_rejects_unknown_source() -> None:
    with pytest.raises(ValueError, match="source"):
        api.fetch_ipsws(source="invalid")  # type: ignore[arg-type]


def test_fetch_ipsws_sorts_and_filters_signed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records: list[api.Firmware] = [
        {
            "device": "iPhone16,2",
            "version": "18.0",
            "buildid": "B",
            "signed": False,
            "filesize": None,
            "url": "https://example.com/b.ipsw",
        },
        {
            "device": "iPhone16,2",
            "version": "17.0",
            "buildid": "A",
            "signed": True,
            "filesize": None,
            "url": "https://example.com/a.ipsw",
        },
    ]

    def fake_fetch(**kwargs: object) -> list[api.Firmware]:
        signed_only = bool(kwargs.get("signed_only"))
        if signed_only:
            return [item for item in records if item["signed"]]
        return list(records)

    monkeypatch.setattr(ipsw_me, "fetch_ipsws", fake_fetch)

    assert api.fetch_ipsws(
        device="iPhone16,2",
        signed_only=True,
        source="ipsw",
    ) == [
        {
            "device": "iPhone16,2",
            "version": "17.0",
            "buildid": "A",
            "signed": True,
            "filesize": None,
            "url": "https://example.com/a.ipsw",
        }
    ]


def test_fetch_ipsws_merges_both_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    ipsw_record: api.Firmware = {
        "device": "iPhone16,2",
        "version": "18.0",
        "buildid": "22A3354",
        "signed": True,
        "filesize": 123,
        "url": "https://example.com/ipsw-me.ipsw",
    }
    appledb_record: api.Firmware = {
        "device": "iPhone99,11",
        "version": "26.5",
        "buildid": "23F77",
        "signed": False,
        "filesize": 456,
        "url": "https://example.com/appledb.ipsw",
    }

    monkeypatch.setattr(ipsw_me, "fetch_ipsws", lambda **kwargs: [ipsw_record])
    monkeypatch.setattr(appledb, "fetch_ipsws", lambda **kwargs: [appledb_record])

    assert api.fetch_ipsws(source="both") == [ipsw_record, appledb_record]


def test_fetch_ipsws_deduplicates_overlapping_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record: api.Firmware = {
        "device": "iPhone16,2",
        "version": "18.0",
        "buildid": "22A3354",
        "signed": True,
        "filesize": 123,
        "url": "https://example.com/shared.ipsw",
    }

    monkeypatch.setattr(ipsw_me, "fetch_ipsws", lambda **kwargs: [record])
    monkeypatch.setattr(appledb, "fetch_ipsws", lambda **kwargs: [record])

    assert api.fetch_ipsws(source="both") == [record]


def test_fetch_ipsws_can_use_appledb_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        appledb,
        "fetch_ipsws",
        lambda **kwargs: [
            {
                "device": "iPhone99,11",
                "version": "26.5",
                "buildid": "23F77",
                "signed": False,
                "filesize": 456,
                "url": "https://example.com/appledb.ipsw",
            }
        ],
    )

    assert api.fetch_ipsws(source="appledb")[0]["device"] == "iPhone99,11"


def test_agents_expose_uniform_contract() -> None:
    for name, agent in api.AGENTS.items():
        assert agent.NAME == name
        assert callable(agent.fetch_ipsws)
