-- One row per place: log entries are grouped by the place's normalized address and
-- coordinates, so two spellings of one place make one pin.
WITH road_traffic (prefix) AS (
    -- The location names a landmark, such as "LEBANON FORD - MIRACLE MILE", but these
    -- events happened on the road, so they are not counted against the place. Parking
    -- lot types (MVA Parking Lot/Private, Parking in Parking Lot) stay with the place
    -- on purpose. A type matches when it starts with one of these, in any case.
    VALUES
        ('Motor Vehicle Stop'),
        ('MV Complaint'),
        ('Assist Motorist'),
        ('MVA Roadway'),
        ('Equip Failure Traffic Light'),
        ('Road Hazard'),
        ('Parking in Roadway'),
        ('Detail Crosswalk'),
        ('Detail Traffic Control')
),
entries AS (
    SELECT
        le.location,
        an.normalized_address,
        an.lat,
        an.lng,
        EXISTS (
            SELECT 1
            FROM road_traffic rt
            WHERE starts_with(lower(le.incident_type), lower(rt.prefix))
        ) AS is_road_traffic
    FROM log_entries le
    JOIN address_normalizations an
        ON le.location = an.raw_address
    WHERE le.parse_error = false
      AND an.lat IS NOT NULL
      AND an.lng IS NOT NULL
)
SELECT
    -- The most common spelling of the place, the first alphabetically on a tie.
    MODE() WITHIN GROUP (ORDER BY location)     AS raw_address,
    normalized_address,
    COUNT(*) FILTER (WHERE NOT is_road_traffic) AS count,
    COUNT(*) FILTER (WHERE is_road_traffic)     AS traffic_count,
    lat,
    lng
FROM entries
GROUP BY normalized_address, lat, lng
ORDER BY count DESC, traffic_count DESC
