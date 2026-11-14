-- One row per incident, with the raw and normalized values side by side (8.12).
-- Left joins, so an entry with no normalization keeps its raw values and has empty
-- normalized columns. Admin only: it carries the officer and the house-level location.
select
    e.entry_id,
    e.case_number,
    e.log_date,
    e.reported_at,
    e.call_source,

    e.raw_incident_type,
    t.category,
    t.normalized_type,
    t.source as incident_type_source,
    t.needs_review as incident_type_needs_review,

    e.disposition,
    e.disposition_unmatched,

    e.raw_location,
    e.place_code,
    l.normalized_address,
    l.kind as location_kind,
    l.street,
    l.lat,
    l.lng,
    l.coordinate_precision,
    l.geocoded_via,
    l.source as location_source,
    l.needs_review as location_needs_review,

    e.officer,
    e.officer_code,
    e.reference_number,
    e.refer_to,
    e.dispatched_at,
    e.enroute_at,
    e.arrived_at,
    e.cleared_at,
    e.response_seconds,
    e.scene_seconds,

    e.missing_from_parse,
    e.parser_version,
    e.source_url,
    e.created_at,
    e.updated_at
    -- TODO(PR 8 task 20): add search_text for admin search.
from {{ ref('stg_log_entries') }} as e
left join {{ ref('stg_incident_types') }} as t
    on t.incident_type_key = e.incident_type_key
left join {{ ref('stg_locations') }} as l
    on l.location_key = e.location_key
