from typing import Literal, get_args

IncidentCategory = Literal["Fire", "EMS", "Police", "Traffic", "Administrative"]
INCIDENT_CATEGORIES: tuple[str, ...] = get_args(IncidentCategory)
