-- 14.5: every public incident is inside the public window, counted back from the
-- newest log date of all incidents, not only the public ones.
select p.case_number, p.log_date
from {{ ref('public_incidents') }} as p
cross join (select max(log_date) as newest from {{ ref('incidents') }}) as n
where p.log_date <= n.newest - {{ var('public_window_days') }}
