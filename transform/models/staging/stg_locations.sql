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
        -- TODO(PR 4 task 10): kind, street, place_code, coordinate_precision, source and
        -- needs_review come with the provenance migration. Until then every location
        -- has no kind, so public_location publishes nothing for it (11.9).
        null::text as kind,
        null::text as street,
        null::text as place_code,
        lat,
        lng,
        null::text as coordinate_precision,
        geocoded_via,
        null::text as source,
        false as needs_review,
        updated_at
    from {{ source('app', 'address_normalizations') }}
) as locations
order by location_key, (source = 'human') desc nulls last, updated_at desc
