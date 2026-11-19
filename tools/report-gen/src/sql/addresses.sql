-- One row per place: log entries are grouped by the place's normalized address and
-- coordinates, so two spellings of one place make one pin.
WITH road_traffic AS (
    -- The location names a landmark, but these events happened on the road. Each is a
    -- prefix, matched in any case. None holds a _ or %, which ILIKE reads as wildcards.
    SELECT ARRAY[
        'Motor Vehicle Stop%',
        'MV Complaint%',
        'Assist Motorist%',
        'MVA Roadway%',
        'Equip Failure Traffic Light%',
        'Road Hazard%',
        'Parking in Roadway%',
        'Detail Crosswalk%',
        'Detail Traffic Control%'
    ] AS patterns
),
entries AS (
    SELECT
        le.location,
        an.normalized_address,
        an.lat,
        an.lng,
        COALESCE(le.incident_type ILIKE ANY (rt.patterns), false) AS is_road_traffic
    FROM log_entries le
    JOIN address_normalizations an
        ON le.location = an.raw_address
    CROSS JOIN road_traffic rt
    WHERE le.parse_error = false
      AND le.reported_at >= CAST($1 AS timestamp)
      AND an.lat IS NOT NULL
      AND an.lng IS NOT NULL
)
SELECT
    -- The most common spelling of the place, the first in sort order on a tie.
    MODE() WITHIN GROUP (ORDER BY location)     AS raw_address,
    normalized_address,
    COUNT(*) FILTER (WHERE NOT is_road_traffic) AS count,
    COUNT(*) FILTER (WHERE is_road_traffic)     AS traffic_count,
    lat,
    lng
FROM entries
GROUP BY normalized_address, lat, lng
ORDER BY count DESC, traffic_count DESC, normalized_address
