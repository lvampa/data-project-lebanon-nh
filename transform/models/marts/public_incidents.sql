-- The public set: incidents in the public window, public columns only (11.2 to 11.10).
-- Field names match today's incidents.json, so the site keeps working (11.5). The
-- held-back fields stay as empty columns, and nothing about provenance is carried (11.4).
with window_start as (
    select max(log_date) - {{ var('public_window_days') }} as after_date
    from {{ ref('incidents') }}
),

in_window as (
    select
        i.*,
        -- A location waiting for review is treated as not normalized, so the incident
        -- is listed with no public location and no pin until it is reviewed (11.19).
        case when i.location_needs_review then null else i.location_kind end
            as public_kind
    from {{ ref('incidents') }} as i
    cross join window_start as w
    where i.log_date > w.after_date
)

select
    case_number,
    log_date,
    reported_at,
    category,
    normalized_type,
    raw_incident_type as incident_type,
    disposition,
    call_source,
    {{ public_location('public_kind', 'normalized_address', 'street') }} as location,
    public_kind as location_kind,
    {{ public_coordinate('public_kind', 'lat', 'street') }} as lat,
    {{ public_coordinate('public_kind', 'lng', 'street') }} as lng,
    -- Empty whenever the coordinates are: not placed, not normalized, or an address
    -- with no matched street (11.8, 11.9).
    case when {{ public_coordinate('public_kind', 'lat', 'street') }} is not null
        then coordinate_precision end as coordinate_precision,
    source_url,
    null::text as officer,
    null::text as reference_number
from in_window
