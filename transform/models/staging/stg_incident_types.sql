-- One row per folded incident type, so the join in `incidents` can never fan out.
-- Raw values that fold together share a value (5.3); a human row wins if they differ.
select distinct on (incident_type_key)
    raw_incident_type,
    incident_type_key,
    category,
    normalized_type,
    source,
    needs_review
from (
    select
        raw_incident_type,
        {{ fold_key('raw_incident_type') }} as incident_type_key,
        category,
        -- TODO(PR 4 task 10): these columns come with the provenance migration.
        null::text as normalized_type,
        null::text as source,
        false as needs_review,
        updated_at
    from {{ source('app', 'incident_type_categories') }}
) as categories
order by incident_type_key, (source = 'human') desc nulls last, updated_at desc
