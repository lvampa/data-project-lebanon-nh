from scripts.models import INCIDENT_CATEGORIES


def test_the_five_categories():
    assert INCIDENT_CATEGORIES == ("Fire", "EMS", "Police", "Traffic", "Administrative")
