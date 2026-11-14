-- 14.5: a public location of kind address is exactly "<Street>" or "<n00> block of
-- <Street>", built from the matched street, so any other text, such as a house number,
-- a unit like "Lot 5", or a note like "Rear", fails it. Its coordinates have at most 3
-- decimal places.
with checked as (
    select
        p.case_number,
        p.location,
        p.lat,
        p.lng,
        initcap(i.street) as street,
        substring(p.location from '^([1-9][0-9]*00) block of ') as hundred
    from {{ ref('public_incidents') }} as p
    join {{ ref('incidents') }} as i using (case_number)
    where p.location_kind = 'address' and p.location is not null
)

select *
from checked
where street is null
    or (
        location is distinct from street
        and location is distinct from hundred || ' block of ' || street
    )
    or lat::numeric <> round(lat::numeric, 3)
    or lng::numeric <> round(lng::numeric, 3)
