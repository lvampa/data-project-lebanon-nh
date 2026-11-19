-- One row per pin, with its report card as JSON. Calls are grouped by the place's
-- normalized address and coordinates, so two spellings of one place make one pin.
-- A road is decided in this order: a ", " in the name means a place; else any spelling
-- the AI called an intersection or highway means a road; else a leading house number
-- means a place; else a bare name is a road. "12 Main St" and "Lebanon Ford, Miracle
-- Mile" are places. The kind comes after the comma because the AI is inconsistent, and
-- before the digit because "1st St and Main" and "89 North" start with one.
WITH entries AS (
    SELECT
        le.location,
        le.reported_at,
        le.incident_type,
        le.disposition,
        le.call_source,
        le.source_url,
        le.case_number,
        le.dispatched_at,
        le.arrived_at,
        le.cleared_at,
        le.officer,
        an.normalized_address,
        an.kind AS address_kind,
        an.lat,
        an.lng,
        call_category(le.incident_type, le.call_source) AS category
    FROM log_entries le
    JOIN address_normalizations an
        ON le.location = an.raw_address
    WHERE le.parse_error = false
      AND le.log_date >= $1
      AND an.lat IS NOT NULL
      AND an.lng IS NOT NULL
),
groups AS (
    SELECT
        normalized_address,
        lat,
        lng,
        -- The most common spelling of the place, the first in sort order on a tie.
        MODE() WITHIN GROUP (ORDER BY location) AS raw_address,
        CASE
            WHEN normalized_address IS NULL
                OR strpos(normalized_address, ', ') > 0
                THEN 'place'
            WHEN bool_or(address_kind IN ('intersection', 'highway')) THEN 'road'
            WHEN normalized_address ~ '^\d' THEN 'place'
            ELSE 'road'
        END AS kind
    FROM entries
    GROUP BY normalized_address, lat, lng
),
slugs AS (
    SELECT
        groups.*,
        COALESCE(
            NULLIF(
                trim(both '-' from lower(regexp_replace(
                    COALESCE(normalized_address, raw_address), '[^A-Za-z0-9]+', '-', 'g'
                ))),
                ''
            ),
            'place'
        ) AS slug
    FROM groups
),
pins AS (
    -- The slug is the id. Pins that share one get a number after "--", which a slug
    -- never holds, so a suffixed id cannot equal another pin's slug. The order is by
    -- place and not by count, so a shared link keeps pointing at the same pin.
    SELECT
        slugs.*,
        CASE
            WHEN row_number() OVER w = 1 THEN slug
            ELSE slug || '--' || row_number() OVER w
        END AS id
    FROM slugs
    WINDOW w AS (PARTITION BY slug ORDER BY lat, lng, normalized_address)
),
tagged AS (
    SELECT entries.*, pins.id AS pin_id, pins.kind
    FROM entries
    JOIN pins
        ON entries.normalized_address IS NOT DISTINCT FROM pins.normalized_address
       AND entries.lat = pins.lat
       AND entries.lng = pins.lng
),
counted AS (
    SELECT
        pin_id,
        COUNT(*) FILTER (WHERE category = 'premises') AS premises,
        COUNT(*) FILTER (WHERE category = 'traffic')  AS traffic,
        COUNT(*) FILTER (WHERE category = 'alarms')   AS alarms,
        COUNT(*) FILTER (WHERE category = 'checks')   AS checks,
        COUNT(*) FILTER (WHERE category = 'admin')    AS admin,
        COUNT(*) FILTER (WHERE category <> 'traffic' OR kind = 'road') AS count
    FROM tagged
    GROUP BY pin_id
)
SELECT
    pins.id,
    pins.kind,
    pins.raw_address,
    pins.normalized_address,
    counted.count,
    counted.traffic AS traffic_count,
    pins.lat,
    pins.lng,
    jsonb_build_object(
        'name', COALESCE(pins.normalized_address, pins.raw_address),
        'kind', pins.kind,
        'lat', pins.lat,
        'lng', pins.lng,
        'count', counted.count,
        'categories', jsonb_build_object(
            'premises', counted.premises,
            'traffic', counted.traffic,
            'alarms', counted.alarms,
            'checks', counted.checks,
            'admin', counted.admin
        ),
        -- What the calls were, for a road, and what happened at the place, for a place.
        'types', (
            SELECT COALESCE(jsonb_agg(jsonb_build_array(incident_type, n)
                                      ORDER BY n DESC, incident_type), '[]')
            FROM (
                SELECT incident_type, COUNT(*) AS n
                FROM tagged
                WHERE pin_id = pins.id
                  AND incident_type IS NOT NULL
                  AND (kind = 'road' OR category = 'premises')
                GROUP BY incident_type
                ORDER BY n DESC, incident_type
                LIMIT 6
            ) top_types
        ),
        'outcomes', (
            SELECT COALESCE(jsonb_agg(jsonb_build_array(disposition, n)
                                      ORDER BY n DESC, disposition), '[]')
            FROM (
                SELECT disposition, COUNT(*) AS n
                FROM tagged
                WHERE pin_id = pins.id
                  AND disposition IS NOT NULL
                  AND (kind = 'road' OR category IN ('premises', 'alarms'))
                GROUP BY disposition
                ORDER BY n DESC, disposition
                LIMIT 5
            ) top_outcomes
        ),
        'calls', (
            SELECT COALESCE(jsonb_agg(jsonb_build_object(
                'reported_at', reported_at,
                'incident_type', incident_type,
                'disposition', disposition,
                'call_source', call_source,
                'category', category,
                'source_url', source_url,
                'case_number', case_number,
                'dispatched_at', dispatched_at,
                'arrived_at', arrived_at,
                'cleared_at', cleared_at,
                'officer', officer
            ) ORDER BY reported_at DESC NULLS LAST), '[]')
            FROM (
                SELECT reported_at, incident_type, disposition, call_source, category,
                       source_url, case_number, dispatched_at, arrived_at, cleared_at,
                       officer
                FROM tagged
                WHERE pin_id = pins.id
                  AND (kind = 'road' OR category <> 'traffic')
                ORDER BY reported_at DESC NULLS LAST, source_url
                LIMIT 10
            ) latest
        )
    )::text AS card
FROM pins
JOIN counted ON counted.pin_id = pins.id
ORDER BY counted.count DESC, counted.traffic DESC, pins.normalized_address, pins.id
