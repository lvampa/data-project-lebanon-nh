"""Tests for PoliceLogItem fields and items package exports."""

from datetime import datetime, timezone

import pytest

from items import PoliceLogItem, UrlRecordItem


def test_police_log_item_has_new_case_number_field():
    item = PoliceLogItem(
        source_url="https://example.com/log.pdf",
        scraped_at=datetime.now(timezone.utc),
        case_number="2024-001",
    )
    assert item["case_number"] == "2024-001"


def test_police_log_item_has_reported_at_field():
    now = datetime.now(timezone.utc)
    item = PoliceLogItem(
        source_url="https://example.com/log.pdf",
        scraped_at=now,
        reported_at=now,
    )
    assert item["reported_at"] == now


def test_police_log_item_has_incident_type_field():
    item = PoliceLogItem(
        source_url="https://example.com/log.pdf",
        scraped_at=datetime.now(timezone.utc),
        incident_type="Theft",
    )
    assert item["incident_type"] == "Theft"


def test_police_log_item_has_location_field():
    item = PoliceLogItem(
        source_url="https://example.com/log.pdf",
        scraped_at=datetime.now(timezone.utc),
        location="123 Main St",
    )
    assert item["location"] == "123 Main St"


def test_police_log_item_has_officer_field():
    item = PoliceLogItem(
        source_url="https://example.com/log.pdf",
        scraped_at=datetime.now(timezone.utc),
        officer="Officer Smith",
    )
    assert item["officer"] == "Officer Smith"


def test_police_log_item_has_disposition_field():
    item = PoliceLogItem(
        source_url="https://example.com/log.pdf",
        scraped_at=datetime.now(timezone.utc),
        disposition="Closed",
    )
    assert item["disposition"] == "Closed"


def test_police_log_item_has_parse_error_field():
    item = PoliceLogItem(
        source_url="https://example.com/log.pdf",
        scraped_at=datetime.now(timezone.utc),
        parse_error="Could not parse date",
    )
    assert item["parse_error"] == "Could not parse date"


def test_items_module_does_not_export_downloaded_url_item():
    import items as items_module

    assert not hasattr(items_module, "DownloadedUrlItem"), (
        "DownloadedUrlItem should not be exported from items module"
    )


def test_items_module_exports_police_log_and_url_record():
    import items as items_module

    assert hasattr(items_module, "PoliceLogItem")
    assert hasattr(items_module, "UrlRecordItem")
