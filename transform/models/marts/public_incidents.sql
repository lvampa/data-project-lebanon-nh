-- The public set: incidents in the public window, public columns only (11.2 to 11.10).
-- Field names match today's incidents.json, so the site keeps working (11.5). The
-- held-back fields stay as empty columns, and nothing about provenance is carried (11.4).
with window_start as (
    select max(log_date) - {{ var('public_window_days') }} as after_date
    from {{ ref('incidents') }}
)

select
    i.case_number,
    i.log_date,
    i.reported_at,
    i.category,
    i.normalized_type,
    i.raw_incident_type as incident_type,
    i.disposition,
    i.call_source,
    {{ public_location('i.location_kind', 'i.normalized_address') }} as location,
    i.location_kind,
    {{ public_coordinate('i.location_kind', 'i.lat') }} as lat,
    {{ public_coordinate('i.location_kind', 'i.lng') }} as lng,
    -- Not placed, or no normalization yet: empty, like the coordinates (11.8, 11.9).
    case when i.location_kind is not null and i.lat is not null
        then i.coordinate_precision end as coordinate_precision,
    i.source_url,
    null::text as officer,
    null::text as reference_number
from {{ ref('incidents') }} as i
cross join window_start as w
where i.log_date > w.after_date
