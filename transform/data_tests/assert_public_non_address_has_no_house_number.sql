-- Safety net for place, intersection and highway, which publish the normalized text as
-- stored (11.7): fail when any comma-separated part starts with a house number, such as
-- "Smith residence, 12 Main St". "Route 120", "I-89 Exit 18" and "1st Ave" pass.
select case_number, location_kind, location
from {{ ref('public_incidents') }}
where location_kind in ('place', 'intersection', 'highway')
    and location ~ '(^|,\s*)[0-9]+[A-Za-z]?\s+[A-Za-z]'
