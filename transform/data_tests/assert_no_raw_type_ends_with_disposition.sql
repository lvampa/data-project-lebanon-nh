-- 14.3: a raw incident type that still ends with a disposition means the parser's split
-- missed it. The seed is generated from the parser's disposition list before each build.
select e.case_number, e.raw_incident_type, d.disposition
from {{ ref('stg_log_entries') }} as e
join {{ ref('dispositions') }} as d
    on lower(e.raw_incident_type) like '%' || lower(d.disposition)
