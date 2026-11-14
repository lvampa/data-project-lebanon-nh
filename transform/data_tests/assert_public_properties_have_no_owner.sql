-- 14.7: no owner name or owner mailing address in the public parcels.
select parcel_id
from {{ ref('public_properties') }}
where owner is not null
    or owner_address is not null
