from unittest.mock import MagicMock, patch
from datetime import datetime

import pytest

from scripts.sync.sync_es import (
    get_address_lookup,
    build_property_doc,
    build_incident_doc,
    build_city_staff_doc,
    build_officer_doc,
    build_llc_doc,
    build_planning_meeting_doc,
    build_planning_document_doc,
    build_budget_line_item_doc,
    build_budget_capital_project_doc,
    sync_index,
)


# --- get_address_lookup ---

def test_get_address_lookup_returns_dict():
    session = MagicMock()
    row = MagicMock()
    row.raw_address = "304 HANOVER ST"
    row.normalized_address = "304 hanover st lebanon nh"
    row.lat = 43.6425
    row.lng = -72.2518
    session.execute.return_value.scalars.return_value.all.return_value = [row]

    result = get_address_lookup(session)

    assert result["304 HANOVER ST"]["normalized_address"] == "304 hanover st lebanon nh"
    assert result["304 HANOVER ST"]["lat"] == 43.6425
    assert result["304 HANOVER ST"]["lng"] == -72.2518


def test_get_address_lookup_empty():
    session = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = []
    assert get_address_lookup(session) == {}


# --- build_property_doc ---

def test_build_property_doc_uses_address_lookup():
    row = MagicMock()
    row.id = 1
    row.parcel_id = "09-123-000"
    row.location = "304 HANOVER ST"
    row.owner = "SMITH JOHN"
    row.owner_address = "304 HANOVER ST LEBANON NH"
    row.land_use = "Single Family"
    row.assessed_total = 450000
    row.year_built = 1985

    lookup = {"304 HANOVER ST": {"normalized_address": "304 hanover st lebanon nh", "lat": 43.64, "lng": -72.25}}
    doc = build_property_doc(row, lookup)

    assert doc["id"] == 1
    assert doc["entity_type"] == "properties"
    assert doc["normalized_address"] == "304 hanover st lebanon nh"
    assert doc["lat"] == 43.64
    assert doc["location"] == "304 HANOVER ST"
    assert doc["owner"] == "SMITH JOHN"


def test_build_property_doc_fallback_when_no_lookup():
    row = MagicMock()
    row.id = 2
    row.location = "UNKNOWN RD"
    row.parcel_id = "09-999"
    row.owner = "DOE JANE"
    row.owner_address = None
    row.land_use = None
    row.assessed_total = None
    row.year_built = None

    doc = build_property_doc(row, {})

    assert doc["normalized_address"] == "UNKNOWN RD"
    assert doc["lat"] is None
    assert doc["lng"] is None


# --- build_incident_doc ---

def test_build_incident_doc_maps_fields():
    row = MagicMock()
    row.id = 10
    row.case_number = "26-00001"
    row.incident_type = "Theft"
    row.location = "MAIN ST"
    row.officer = "Jones"
    row.disposition = "Report Taken"
    row.reported_at = datetime(2026, 1, 1, 10, 0)
    row.raw_text = "some raw text"

    doc = build_incident_doc(row, {})

    assert doc["id"] == 10
    assert doc["entity_type"] == "incidents"
    assert doc["case_number"] == "26-00001"
    assert doc["incident_type"] == "Theft"
    assert doc["normalized_address"] == "MAIN ST"


# --- build_city_staff_doc ---

def test_build_city_staff_doc():
    row = MagicMock()
    row.id = 5
    row.name = "Alice Martin"
    row.title = "City Manager"
    row.department = "Administration"
    row.division = None

    doc = build_city_staff_doc(row)

    assert doc["id"] == 5
    assert doc["entity_type"] == "city_staff"
    assert doc["name"] == "Alice Martin"
    assert doc["title"] == "City Manager"
    assert "lat" not in doc


# --- build_officer_doc ---

def test_build_officer_doc():
    row = MagicMock()
    row.id = 7
    row.name = "Bob Chen"
    row.rank = "Sergeant"
    row.division = "Patrol"

    doc = build_officer_doc(row)

    assert doc["entity_type"] == "officers"
    assert doc["rank"] == "Sergeant"


# --- build_llc_doc ---

def test_build_llc_doc():
    row = MagicMock()
    row.id = 3
    row.name = "MAIN ST LLC"
    row.raw_owner_name = "Main St LLC"

    doc = build_llc_doc(row)

    assert doc["entity_type"] == "llcs"
    assert doc["name"] == "MAIN ST LLC"


# --- build_planning_meeting_doc ---

def test_build_planning_meeting_doc_inherits_address_from_lookup():
    row = MagicMock()
    row.id = 20
    row.civicclerk_event_id = 9001
    row.title = "Planning Board Meeting"
    row.category = "Planning Board"
    row.meeting_date = datetime(2026, 3, 15)
    row.location = "City Hall"
    row.status = "Published"

    doc = build_planning_meeting_doc(row, {})

    assert doc["entity_type"] == "planning_meetings"
    assert doc["title"] == "Planning Board Meeting"
    assert doc["normalized_address"] == "City Hall"


# --- build_planning_document_doc ---

def test_build_planning_document_doc():
    row = MagicMock()
    row.id = 30
    row.civicclerk_file_id = 555
    row.civicclerk_event_id = 9001
    row.file_name = "Variance Application"
    row.file_type = "PDF"
    row.raw_text = "applicant requests variance at 304 hanover st"

    meeting_lookup = {9001: {"normalized_address": "304 hanover st lebanon nh", "lat": 43.64, "lng": -72.25}}
    doc = build_planning_document_doc(row, meeting_lookup)

    assert doc["entity_type"] == "planning_documents"
    assert doc["file_name"] == "Variance Application"
    assert doc["normalized_address"] == "304 hanover st lebanon nh"


# --- build_budget_line_item_doc ---

def test_build_budget_line_item_doc():
    row = MagicMock()
    row.id = 40
    row.fiscal_year = 2026
    row.department = "City Clerk"
    row.description = "FULL TIME WAGES"
    row.fund_name = "General Fund"

    doc = build_budget_line_item_doc(row)

    assert doc["entity_type"] == "budget_line_items"
    assert doc["fiscal_year"] == 2026
    assert doc["description"] == "FULL TIME WAGES"


# --- build_budget_capital_project_doc ---

def test_build_budget_capital_project_doc():
    row = MagicMock()
    row.id = 50
    row.fiscal_year = 2026
    row.project_name = "TRUES BROOK BRIDGE"
    row.fund_name = "CIP"

    doc = build_budget_capital_project_doc(row)

    assert doc["entity_type"] == "budget_capital_projects"
    assert doc["project_name"] == "TRUES BROOK BRIDGE"


# --- sync_index ---

def test_sync_index_calls_bulk():
    es = MagicMock()

    rows = [MagicMock(id=1), MagicMock(id=2)]
    build_fn = lambda row: {"id": row.id, "entity_type": "test", "name": "foo"}

    with patch("scripts.sync.sync_es.bulk") as mock_bulk:
        mock_bulk.return_value = (2, [])
        count = sync_index(es, "test_index", rows, build_fn)

    assert count == 2
    mock_bulk.assert_called_once()
    call_args = mock_bulk.call_args
    actions = list(call_args[0][1])
    assert len(actions) == 2
    assert actions[0]["_id"] == "1"
    assert actions[0]["_index"] == "test_index"


def test_sync_index_noop_on_empty():
    es = MagicMock()
    with patch("scripts.sync.sync_es.bulk") as mock_bulk:
        count = sync_index(es, "test_index", [], lambda r: {})
    assert count == 0
    mock_bulk.assert_not_called()
