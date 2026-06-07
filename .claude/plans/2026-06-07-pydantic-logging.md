# Pydantic Validation Models + Logfire Logging

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Pydantic validation models (Pattern A — validate in pipeline, keep `scrapy.Item` as transport) for all four item types, and replace `print()` with `logfire` in `generate_web_data.py`.

**Architecture:** Scrapy Items remain unchanged. Each pipeline calls `Model.model_validate(dict(item))` at the persistence boundary, gaining typed fields, auto whitespace-stripping, and coercion. `_parse_sale_date` in `pipelines.py` moves into `SaleRecord` as a `@field_validator`. The `generate_web_data.py` script gets a `logfire.span()` around `main()` and structured `logfire.info()` calls replacing `print()`.

---

## What already exists (do not re-implement)

| Component | File | Notes |
|-----------|------|-------|
| Scrapy Items | `scrapers/items/*.py` | Stay as-is — raw transport layer |
| LogfireExtension | `scrapers/extensions.py` | Already configured, instruments pymongo |
| UrlDocument | `scrapers/models/url_document.py` | MongoDB doc model — not changed |
| Pipelines | `scrapers/pipelines.py` | Modified to use new models |
| generate_web_data | `scripts/generate_web_data.py` | Modified for logfire |

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `scrapers/models/property.py` | Create | `SaleRecord` + `PropertyRecord` Pydantic models |
| `scrapers/models/police_log.py` | Create | `PoliceLogRecord` Pydantic model |
| `scrapers/models/city_staff.py` | Create | `CityStaffRecord` Pydantic model |
| `scrapers/models/url_record.py` | Create | `UrlRecord` Pydantic model |
| `scrapers/models/__init__.py` | Create/update | Export all four models |
| `scrapers/tests/test_property_record.py` | Create | Tests for PropertyRecord + SaleRecord |
| `scrapers/tests/test_police_log_record.py` | Create | Tests for PoliceLogRecord |
| `scrapers/tests/test_city_staff_record.py` | Create | Tests for CityStaffRecord |
| `scrapers/tests/test_url_record_model.py` | Create | Tests for UrlRecord |
| `scrapers/pipelines.py` | Modify | Use model_validate in each pipeline, delete _parse_sale_date |
| `scripts/generate_web_data.py` | Modify | Replace print() with logfire |

---

## Pydantic Conventions (apply to all models)

- `model_config = ConfigDict(str_strip_whitespace=True)` on every model
- Required fields: no default. Optional fields: `= None` with `| None` type.
- Use `model_validate(dict(item))` in pipelines — never `Model(**dict(item))`
- Use `@field_validator(mode="before")` for coercion, `@classmethod` required
- `Field(default_factory=list)` for list fields
- All validators must handle `None` gracefully — never raise on missing optional data

---

### Task 1: PropertyRecord + SaleRecord

**Files:**
- Create: `scrapers/models/property.py`
- Create: `scrapers/tests/test_property_record.py`

- [ ] **Step 1: Write failing tests**

Create `scrapers/tests/test_property_record.py`:

```python
import pytest
from datetime import date
from pydantic import ValidationError
from models.property import PropertyRecord, SaleRecord


def make_property(**kwargs):
    defaults = dict(
        parcel_id="10001",
        location="  123 MAIN ST  ",
        owner="SMITH, JOHN",
        owner_address="PO BOX 1, LEBANON NH 03766",
        land_use="101 - Res 1 Family",
        lot_size_acres=0.25,
        year_built=1985,
        building_sqft=1450,
        assessed_land=100000,
        assessed_building=250000,
        assessed_total=350000,
        assessment_year=2025,
        detail_url="https://gis.vgsi.com/LebanonNH/Parcel.aspx?Pid=10001",
        sales=[],
    )
    return {**defaults, **kwargs}


def test_property_record_shape():
    record = PropertyRecord.model_validate(make_property())
    assert record.parcel_id == "10001"
    assert record.assessed_total == 350000
    assert record.sales == []


def test_property_record_strips_whitespace():
    record = PropertyRecord.model_validate(make_property(location="  123 MAIN ST  "))
    assert record.location == "123 MAIN ST"


def test_property_record_null_fields():
    record = PropertyRecord.model_validate(make_property(location=None, assessed_total=None, lot_size_acres=None))
    assert record.location is None
    assert record.assessed_total is None
    assert record.lot_size_acres is None


def test_property_record_missing_parcel_id_raises():
    data = make_property()
    del data["parcel_id"]
    with pytest.raises(ValidationError):
        PropertyRecord.model_validate(data)


def test_sale_record_parses_date_string():
    sale = SaleRecord.model_validate({"sale_date": "06/15/2021", "sale_price": 350000})
    assert sale.sale_date == date(2021, 6, 15)


def test_sale_record_bad_date_returns_none():
    sale = SaleRecord.model_validate({"sale_date": "not-a-date"})
    assert sale.sale_date is None


def test_sale_record_null_date_returns_none():
    sale = SaleRecord.model_validate({"sale_date": None})
    assert sale.sale_date is None


def test_property_record_sales_parsed():
    record = PropertyRecord.model_validate(make_property(sales=[
        {"sale_date": "01/01/2020", "sale_price": 200000, "grantee": "JONES", "grantor": "SMITH"}
    ]))
    assert len(record.sales) == 1
    assert record.sales[0].sale_date == date(2020, 1, 1)
    assert record.sales[0].sale_price == 200000
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/connor/projects/data-project && uv run pytest scrapers/tests/test_property_record.py -v 2>&1 | tail -10
```

Expected: ImportError — `models.property` does not exist yet.

- [ ] **Step 3: Create `scrapers/models/property.py`**

```python
from datetime import date
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SaleRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    sale_date: date | None = None
    sale_price: int | None = None
    grantee: str | None = None
    grantor: str | None = None

    @field_validator("sale_date", mode="before")
    @classmethod
    def parse_sale_date(cls, v: object) -> date | None:
        if not isinstance(v, str):
            return v
        try:
            m, d, y = v.strip().split("/")
            return date(int(y), int(m), int(d))
        except Exception:
            return None


class PropertyRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    parcel_id: str
    location: str | None = None
    owner: str | None = None
    owner_address: str | None = None
    land_use: str | None = None
    lot_size_acres: float | None = None
    year_built: int | None = None
    building_sqft: int | None = None
    assessed_land: int | None = None
    assessed_building: int | None = None
    assessed_total: int | None = None
    assessment_year: int | None = None
    detail_url: str | None = None
    sales: list[SaleRecord] = Field(default_factory=list)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd /Users/connor/projects/data-project && uv run pytest scrapers/tests/test_property_record.py -v 2>&1 | tail -15
```

Expected: 8 tests PASSED.

- [ ] **Step 5: Commit**

```bash
cd /Users/connor/projects/data-project
git add scrapers/models/property.py scrapers/tests/test_property_record.py
git commit -m "$(cat <<'EOF'
feat: add PropertyRecord + SaleRecord Pydantic models

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: PoliceLogRecord

**Files:**
- Create: `scrapers/models/police_log.py`
- Create: `scrapers/tests/test_police_log_record.py`

- [ ] **Step 1: Write failing tests**

Create `scrapers/tests/test_police_log_record.py`:

```python
import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from models.police_log import PoliceLogRecord


def make_log(**kwargs):
    defaults = dict(
        source_url="https://example.com/log.pdf",
        scraped_at=datetime.now(timezone.utc),
        case_number="2025-001",
        reported_at=datetime.now(timezone.utc),
        call_source="911",
        incident_type="TRAFFIC STOP",
        disposition="GONE ON ARRIVAL",
        raw_reason_action="SPEEDING",
        location="123 MAIN ST",
        officer="SMITH",
        reference_number="REF-001",
        dispatched_at=None,
        enroute_at=None,
        arrived_at=None,
        cleared_at=None,
        response_seconds=None,
        scene_seconds=None,
        raw_text="raw text here",
        parse_error=False,
    )
    return {**defaults, **kwargs}


def test_police_log_record_shape():
    record = PoliceLogRecord.model_validate(make_log())
    assert record.source_url == "https://example.com/log.pdf"
    assert record.incident_type == "TRAFFIC STOP"
    assert record.parse_error is False


def test_police_log_record_parse_error_defaults_false():
    data = make_log()
    del data["parse_error"]
    record = PoliceLogRecord.model_validate(data)
    assert record.parse_error is False


def test_police_log_record_null_optional_fields():
    record = PoliceLogRecord.model_validate(make_log(
        case_number=None, incident_type=None, location=None
    ))
    assert record.case_number is None
    assert record.incident_type is None
    assert record.location is None


def test_police_log_record_strips_whitespace():
    record = PoliceLogRecord.model_validate(make_log(location="  MAIN ST  "))
    assert record.location == "MAIN ST"


def test_police_log_record_missing_source_url_raises():
    data = make_log()
    del data["source_url"]
    with pytest.raises(ValidationError):
        PoliceLogRecord.model_validate(data)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/connor/projects/data-project && uv run pytest scrapers/tests/test_police_log_record.py -v 2>&1 | tail -10
```

Expected: ImportError.

- [ ] **Step 3: Create `scrapers/models/police_log.py`**

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class PoliceLogRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    source_url: str
    scraped_at: datetime
    case_number: str | None = None
    reported_at: datetime | None = None
    call_source: str | None = None
    incident_type: str | None = None
    disposition: str | None = None
    raw_reason_action: str | None = None
    location: str | None = None
    officer: str | None = None
    reference_number: str | None = None
    dispatched_at: datetime | None = None
    enroute_at: datetime | None = None
    arrived_at: datetime | None = None
    cleared_at: datetime | None = None
    response_seconds: int | None = None
    scene_seconds: int | None = None
    raw_text: str | None = None
    parse_error: bool = False
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd /Users/connor/projects/data-project && uv run pytest scrapers/tests/test_police_log_record.py -v 2>&1 | tail -10
```

Expected: 5 tests PASSED.

- [ ] **Step 5: Commit**

```bash
cd /Users/connor/projects/data-project
git add scrapers/models/police_log.py scrapers/tests/test_police_log_record.py
git commit -m "$(cat <<'EOF'
feat: add PoliceLogRecord Pydantic model

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: CityStaffRecord + UrlRecord

**Files:**
- Create: `scrapers/models/city_staff.py`
- Create: `scrapers/models/url_record.py`
- Create: `scrapers/tests/test_city_staff_record.py`
- Create: `scrapers/tests/test_url_record_model.py`

- [ ] **Step 1: Write failing tests for both models**

Create `scrapers/tests/test_city_staff_record.py`:

```python
import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from models.city_staff import CityStaffRecord


def make_staff(**kwargs):
    defaults = dict(
        name="Jane Smith",
        title="Chief of Police",
        department="Police",
        division="Patrol",
        email="jane@lebanon.gov",
        phone="603-555-0100",
        source_url="https://www.lebcity.com/staff",
        scraped_at=datetime.now(timezone.utc),
    )
    return {**defaults, **kwargs}


def test_city_staff_record_shape():
    record = CityStaffRecord.model_validate(make_staff())
    assert record.name == "Jane Smith"
    assert record.department == "Police"


def test_city_staff_record_strips_whitespace():
    record = CityStaffRecord.model_validate(make_staff(name="  Jane Smith  "))
    assert record.name == "Jane Smith"


def test_city_staff_record_null_optional_fields():
    record = CityStaffRecord.model_validate(make_staff(title=None, division=None, email=None, phone=None))
    assert record.title is None
    assert record.division is None


def test_city_staff_record_missing_required_raises():
    data = make_staff()
    del data["name"]
    with pytest.raises(ValidationError):
        CityStaffRecord.model_validate(data)
```

Create `scrapers/tests/test_url_record_model.py`:

```python
import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from models.url_record import UrlRecord


def make_url(**kwargs):
    defaults = dict(
        canonical_url="https://example.com/log.pdf",
        archive_url=None,
        log_date=None,
        state="pending",
        created_at=datetime.now(timezone.utc),
    )
    return {**defaults, **kwargs}


def test_url_record_shape():
    record = UrlRecord.model_validate(make_url())
    assert record.canonical_url == "https://example.com/log.pdf"
    assert record.state == "pending"


def test_url_record_null_optional_fields():
    record = UrlRecord.model_validate(make_url(archive_url=None, log_date=None))
    assert record.archive_url is None
    assert record.log_date is None


def test_url_record_missing_canonical_url_raises():
    data = make_url()
    del data["canonical_url"]
    with pytest.raises(ValidationError):
        UrlRecord.model_validate(data)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/connor/projects/data-project && uv run pytest scrapers/tests/test_city_staff_record.py scrapers/tests/test_url_record_model.py -v 2>&1 | tail -10
```

Expected: ImportError for both.

- [ ] **Step 3: Create `scrapers/models/city_staff.py`**

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class CityStaffRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str
    department: str
    source_url: str
    scraped_at: datetime
    title: str | None = None
    division: str | None = None
    email: str | None = None
    phone: str | None = None
```

- [ ] **Step 4: Create `scrapers/models/url_record.py`**

```python
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict


class UrlRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    canonical_url: str
    state: Literal["pending", "in_progress", "complete", "error"]
    created_at: datetime
    archive_url: str | None = None
    log_date: date | None = None
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
cd /Users/connor/projects/data-project && uv run pytest scrapers/tests/test_city_staff_record.py scrapers/tests/test_url_record_model.py -v 2>&1 | tail -10
```

Expected: 7 tests PASSED.

- [ ] **Step 6: Update `scrapers/models/__init__.py`**

The file already exists. Read it first, then add exports for all new models (preserve any existing exports such as `UrlDocument`):

```python
from .city_staff import CityStaffRecord
from .police_log import PoliceLogRecord
from .property import PropertyRecord, SaleRecord
from .url_record import UrlRecord

__all__ = ["CityStaffRecord", "PoliceLogRecord", "PropertyRecord", "SaleRecord", "UrlRecord"]
```

- [ ] **Step 7: Commit**

```bash
cd /Users/connor/projects/data-project
git add scrapers/models/city_staff.py scrapers/models/url_record.py scrapers/models/__init__.py \
        scrapers/tests/test_city_staff_record.py scrapers/tests/test_url_record_model.py
git commit -m "$(cat <<'EOF'
feat: add CityStaffRecord and UrlRecord Pydantic models

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Wire models into pipelines.py

**Files:**
- Modify: `scrapers/pipelines.py`

No new tests in this task — the existing pipeline tests cover behavior. The full scraper test suite is the verification gate.

- [ ] **Step 1: Update `UrlRecordPipeline`**

Add import at top of `pipelines.py`:
```python
from models.url_record import UrlRecord
from models.property import PropertyRecord
from models.police_log import PoliceLogRecord
from models.city_staff import CityStaffRecord
```

In `UrlRecordPipeline.process_item`, add validation before building the `UpdateOne`:
```python
def process_item(self, item, spider):
    if not isinstance(item, UrlRecordItem):
        return item
    record = UrlRecord.model_validate(dict(item))
    self._count += 1
    self._ops.append(
        UpdateOne(
            {"canonical_url": record.canonical_url},
            {"$setOnInsert": {
                "canonical_url": record.canonical_url,
                "archive_url": record.archive_url,
                "log_date": record.log_date,
                "state": record.state,
                "created_at": record.created_at,
            }},
            upsert=True,
        )
    )
    return item
```

- [ ] **Step 2: Update `PoliceLogPipeline`**

In `PoliceLogPipeline.process_item`, validate and use typed fields:
```python
def process_item(self, item, spider):
    if not isinstance(item, PoliceLogItem):
        return item
    record = PoliceLogRecord.model_validate(dict(item))
    with logfire.span("save police log entry", source_url=record.source_url):
        stmt = pg_insert(LogEntry).values(
            source_url=record.source_url,
            case_number=record.case_number,
            reported_at=record.reported_at,
            call_source=record.call_source,
            incident_type=record.incident_type,
            disposition=record.disposition,
            raw_reason_action=record.raw_reason_action,
            location=record.location,
            officer=record.officer,
            reference_number=record.reference_number,
            dispatched_at=record.dispatched_at,
            enroute_at=record.enroute_at,
            arrived_at=record.arrived_at,
            cleared_at=record.cleared_at,
            response_seconds=record.response_seconds,
            scene_seconds=record.scene_seconds,
            raw_text=record.raw_text,
            parse_error=record.parse_error,
            scraped_at=record.scraped_at,
        ).on_conflict_do_nothing(index_elements=["case_number"])
        self._session.execute(stmt)
    return item
```

- [ ] **Step 3: Update `PropertyPipeline` and delete `_parse_sale_date`**

Delete the `_parse_sale_date` standalone function entirely — it now lives in `SaleRecord`.

Update `PropertyPipeline.process_item`:
```python
def process_item(self, item, spider):
    if not isinstance(item, PropertyItem):
        return item
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        record = PropertyRecord.model_validate(dict(item))
        with logfire.span("save property", parcel_id=record.parcel_id):
            stmt = pg_insert(Property).values(
                parcel_id=record.parcel_id,
                location=record.location,
                owner=record.owner,
                owner_address=record.owner_address,
                land_use=record.land_use,
                lot_size_acres=record.lot_size_acres,
                year_built=record.year_built,
                building_sqft=record.building_sqft,
                assessed_land=record.assessed_land,
                assessed_building=record.assessed_building,
                assessed_total=record.assessed_total,
                assessment_year=record.assessment_year,
                detail_url=record.detail_url,
                created_at=now,
                updated_at=now,
            ).on_conflict_do_update(
                index_elements=["parcel_id"],
                set_={
                    "location": record.location,
                    "owner": record.owner,
                    "owner_address": record.owner_address,
                    "land_use": record.land_use,
                    "lot_size_acres": record.lot_size_acres,
                    "year_built": record.year_built,
                    "building_sqft": record.building_sqft,
                    "assessed_land": record.assessed_land,
                    "assessed_building": record.assessed_building,
                    "assessed_total": record.assessed_total,
                    "assessment_year": record.assessment_year,
                    "detail_url": record.detail_url,
                    "updated_at": now,
                },
            )
            self._session.execute(stmt)
            property_id = self._session.execute(
                select(Property.id).where(Property.parcel_id == record.parcel_id)
            ).scalar_one()
            self._session.execute(
                delete(PropertySale).where(PropertySale.property_id == property_id)
            )
            for sale in record.sales:
                self._session.execute(
                    pg_insert(PropertySale).values(
                        property_id=property_id,
                        sale_date=sale.sale_date,
                        sale_price=sale.sale_price,
                        grantee=sale.grantee,
                        grantor=sale.grantor,
                        created_at=now,
                    )
                )
    except Exception:
        self._session.rollback()
        raise
    return item
```

- [ ] **Step 4: Update `CityStaffPipeline`**

```python
def process_item(self, item, spider):
    if not isinstance(item, CityStaffItem):
        return item
    try:
        record = CityStaffRecord.model_validate(dict(item))
        with logfire.span("save city staff", name=record.name, department=record.department):
            stmt = pg_insert(CityStaff).values(
                name=record.name,
                title=record.title,
                department=record.department,
                division=record.division,
                email=record.email,
                phone=record.phone,
                source_url=record.source_url,
                scraped_at=record.scraped_at,
            ).on_conflict_do_update(
                constraint="uq_city_staff_name_dept",
                set_={
                    "title": record.title,
                    "division": record.division,
                    "email": record.email,
                    "phone": record.phone,
                    "source_url": record.source_url,
                    "scraped_at": record.scraped_at,
                },
            )
            self._session.execute(stmt)
    except Exception:
        self._session.rollback()
        raise
    return item
```

- [ ] **Step 5: Run the full scraper test suite**

```bash
cd /Users/connor/projects/data-project/scrapers && uv run pytest -v 2>&1 | tail -15
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/connor/projects/data-project
git add scrapers/pipelines.py
git commit -m "$(cat <<'EOF'
refactor: wire Pydantic validation models into all pipelines

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Logfire logging in generate_web_data.py

**Files:**
- Modify: `scripts/generate_web_data.py`

No new tests — the existing `test_generate_web_data.py` tests cover `format_*` functions, which are unchanged. The verification gate is those tests still passing.

- [ ] **Step 1: Add logfire import and update `_write`**

At the top of `scripts/generate_web_data.py`, add:
```python
import logfire
```

Replace the `_write` function:
```python
def _write(filename: str, data: object) -> None:
    path = OUT_DIR / filename
    path.write_text(json.dumps(data, default=str), encoding="utf-8")
    logfire.info(
        "wrote {filename}",
        filename=filename,
        bytes=path.stat().st_size,
        records=len(data) if isinstance(data, list) else None,
    )
```

- [ ] **Step 2: Wrap `main()` in a logfire span**

The existing `main()` body moves inside a `logfire.span`. The `db` session and all query/`_write` calls are unchanged — only the function signature gains `logfire.configure()` at the top and a `with logfire.span(...)` wrapping the entire body:

```python
def main() -> None:
    logfire.configure()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with logfire.span("generate web data"):
        db: Session = SessionLocal()
        try:
            # all existing query and _write calls go here, indented one level
        finally:
            db.close()
```

Read the current `main()` in `scripts/generate_web_data.py`, add `logfire.configure()` before `OUT_DIR.mkdir`, then wrap the `db = SessionLocal()` line through the closing `db.close()` in a `with logfire.span("generate web data"):` block (one extra indent level).

- [ ] **Step 3: Run existing tests to confirm nothing broke**

```bash
cd /Users/connor/projects/data-project && uv run pytest scripts/tests/test_generate_web_data.py -v 2>&1 | tail -10
```

Expected: 8 tests PASSED.

- [ ] **Step 4: Commit**

```bash
cd /Users/connor/projects/data-project
git add scripts/generate_web_data.py
git commit -m "$(cat <<'EOF'
feat: replace print() with logfire in generate_web_data script

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```
