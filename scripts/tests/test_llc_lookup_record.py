from datetime import date

import pytest
from pydantic import ValidationError

from scripts.models import LlcLookupRecord


def test_accepts_parsed_detail_page():
    record = LlcLookupRecord.model_validate(
        {
            "nh_business_id": "775794",
            "business_status": "Good Standing",
            "formation_date": date(2017, 7, 28),
            "business_email": "dick@anagnost.com",
            "phone": "603-669-6194",
            "registered_agent": "Kenneth A. Viscarello Esq.",
            "registered_agent_address": "1000 Elm Street, Manchester, NH",
            "principals": [
                {
                    "name": "dick anagnost",
                    "title": "Manager",
                    "address": "1662 elm st, Manchester, NH, 03101, USA",
                }
            ],
        }
    )
    assert record.model_dump()["principals"] == [
        {
            "name": "dick anagnost",
            "title": "Manager",
            "address": "1662 elm st, Manchester, NH, 03101, USA",
        }
    ]


def test_allows_empty_lookup():
    record = LlcLookupRecord.model_validate({"principals": None})
    assert record.nh_business_id is None
    assert record.principals is None


def test_rejects_principal_without_name():
    with pytest.raises(ValidationError, match="name"):
        LlcLookupRecord.model_validate(
            {"principals": [{"name": " ", "title": "Manager", "address": None}]}
        )


def test_rejects_unparsed_formation_date():
    with pytest.raises(ValidationError, match="formation_date"):
        LlcLookupRecord.model_validate({"formation_date": "sometime in 2017"})
