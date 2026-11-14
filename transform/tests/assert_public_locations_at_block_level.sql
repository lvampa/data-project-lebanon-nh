-- 14.5: no public location of kind address starts with a number that isn't a multiple
-- of 100, and no address coordinate has more than 3 decimal places.
select case_number, location, lat, lng
from {{ ref('public_incidents') }}
where location_kind = 'address'
    and (
        (location ~ '^\d' and (substring(location from '^(\d+)'))::bigint % 100 <> 0)
        or lat::numeric <> round(lat::numeric, 3)
        or lng::numeric <> round(lng::numeric, 3)
    )
