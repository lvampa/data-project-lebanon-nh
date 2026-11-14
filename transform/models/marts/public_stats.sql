-- Counts over the public window only, by category, normalized type name and weekday
-- (11.11). One long table; report-gen shapes it into stats.json.
-- An incident with no normalization yet counts under an empty category or type name.
select 'category' as dimension, category as value, count(*) as count
from {{ ref('public_incidents') }}
group by category

union all

select 'normalized_type' as dimension, normalized_type as value, count(*) as count
from {{ ref('public_incidents') }}
group by normalized_type

union all

-- 0 is Sunday, as report-gen's weekday names expect.
select 'weekday' as dimension, extract(dow from reported_at)::int::text as value, count(*) as count
from {{ ref('public_incidents') }}
where reported_at is not null
group by extract(dow from reported_at)
