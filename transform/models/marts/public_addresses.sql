-- Today's addresses.json shape, built only from the public set (11.12).
-- raw_address and normalized_address both hold the public location: the raw value can
-- be a house address, so it never leaves the admin.
select
    location as raw_address,
    location as normalized_address,
    count(*) as count,
    lat,
    lng
from {{ ref('public_incidents') }}
where location is not null
    and lat is not null
    and lng is not null
group by location, lat, lng
