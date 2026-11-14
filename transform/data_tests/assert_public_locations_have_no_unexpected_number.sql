-- 14.9: no public location carries a number other than one of four allowed forms, the
-- same allowlist as `report-gen check` (tools/report-gen/src/check.rs). Every run of
-- digits must be one of:
--   a. a block hundred at the start or after a comma: "1200 block of Main St";
--   b. an ordinal: "1st Ave", "11th St";
--   c. a road number after route, rte, rt, nh, us, vt, i or interstate: "I-89", "NH Route 12A";
--   d. an exit or mile number after exit, mile or marker: "Exit 18", "mile marker 12".
-- The allowed forms are stripped, and any digit left fails, as does any non-ASCII digit,
-- so "Smith Residence at 12 Main St", "12-14 Main St", "No. 12", "#12" and "Unit 4" fail.
with stripped as (
    select
        case_number,
        location_kind,
        location,
        regexp_replace(
            regexp_replace(
                regexp_replace(
                    regexp_replace(
                        location,
                        '(^|,)\s*[1-9][0-9]*00 block of ', '\1', 'gi'),
                    '[0-9]+(st|nd|rd|th)(?![a-z])', '', 'gi'),
                '\m(route|rte|rt|nh|us|vt|i|interstate)([\s.-]*)[0-9]+', '\1\2', 'gi'),
            '\m(exit|mile|marker)([\s.-]*)[0-9]+', '\1\2', 'gi'
        ) as remainder
    from {{ ref('public_incidents') }}
    where location is not null
)

select case_number, location_kind, location, remainder
from stripped
where remainder ~ '[0-9]'
    -- Full-width, Arabic-Indic and extended Arabic-Indic digits, checked explicitly
    -- because [[:digit:]] depends on the database locale.
    or location ~ '[０-９٠-٩۰-۹]'
