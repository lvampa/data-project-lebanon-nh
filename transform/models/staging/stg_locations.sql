-- One row per folded raw location, so the join in `incidents` can never fan out.
-- A human row wins over a rule or AI row for the same folded value.
select distinct on (location_key)
    raw_address,
    location_key,
    normalized_address,
    kind,
    street,
    place_code,
    lat,
    lng,
    coordinate_precision,
    geocoded_via,
    source,
    needs_review
from (
    select
        raw_address,
        {{ fold_key('raw_address') }} as location_key,
        normalized_address,
        kind,
        street,
        place_code,
        lat,
        lng,
        coordinate_precision,
        geocoded_via,
        source,
        needs_review,
        updated_at
    from {{ source('app', 'address_normalizations') }}
) as locations
order by location_key, (source = 'human') desc nulls last, updated_at desc
