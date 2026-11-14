-- The public set of parcels for properties.json (11.13 to 11.15).
-- Owner names and owner mailing addresses are mostly residents', so they stay in the
-- admin. The two fields remain as empty columns so the site's PropertyRecord type keeps
-- working until the frontend drops them.
select
    parcel_id,
    location,
    null::text as owner,
    null::text as owner_address,
    land_use,
    lot_size_acres::float8 as lot_size_acres,
    year_built,
    building_sqft,
    assessed_land,
    assessed_building,
    assessed_total,
    assessment_year,
    detail_url
from {{ source('app', 'properties') }}
