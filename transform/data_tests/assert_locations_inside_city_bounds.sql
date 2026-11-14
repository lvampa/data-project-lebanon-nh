-- 14.2: coordinates outside the city bounds fail the build unless Connor set them by hand.
{% set b = var('city_bounds') %}
select raw_address, lat, lng, geocoded_via
from {{ ref('stg_locations') }}
where lat is not null
    and lng is not null
    and geocoded_via is distinct from 'manual'
    and not (
        lat between {{ b.min_lat }} and {{ b.max_lat }}
        and lng between {{ b.min_lng }} and {{ b.max_lng }}
    )
