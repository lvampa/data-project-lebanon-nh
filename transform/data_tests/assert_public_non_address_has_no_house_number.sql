-- Safety net for place, intersection and highway, which publish the normalized text as
-- stored (11.7): fail when a house number is followed, within a few words, by a street
-- suffix, such as "Smith residence, 12 Main St" or "Smith Residence 12 Main St".
-- "Route 120", "I-89 Exit 18", "mile marker 18" and "Route 4 Market Basket" pass.
select case_number, location_kind, location
from {{ ref('public_incidents') }}
where location_kind in ('place', 'intersection', 'highway')
    and location ~* '\m[0-9]+[A-Za-z]?\s+([A-Za-z]+\s+)*?(St|Street|Rd|Road|Ave|Avenue|Dr|Drive|Ln|Lane|Ct|Court|Way|Pl|Place|Cir|Ter|Hwy)\M'
