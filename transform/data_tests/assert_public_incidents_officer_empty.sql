-- 14.5 and 11.4: no officer name or reference number in the public set.
select case_number, officer, reference_number
from {{ ref('public_incidents') }}
where officer is not null
    or reference_number is not null
