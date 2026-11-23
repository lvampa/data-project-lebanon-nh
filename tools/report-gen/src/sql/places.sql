-- One row per pin, with its report card as JSON. Calls are grouped by the place's
-- normalized address and coordinates, so two spellings of one place make one pin.
-- It reads the public views only. A location the views flag has no pin and no name of its
-- own: its calls count on its street's pin, and are left out when the street has none.
-- A road is decided in this order: a ", " in the name means a place; else any spelling
-- the AI called an intersection or highway means a road; else a leading house number
-- means a place; else a bare name is a road. "12 Main St" and "Lebanon Ford, Miracle
-- Mile" are places. The kind comes after the comma because the AI is inconsistent, and
-- before the digit because "1st St and Main" and "89 North" start with one.
WITH entries AS (
    SELECT
        le.location,
        le.log_date,
        le.reported_at,
        le.incident_type,
        le.raw_incident_type,
        le.disposition,
        le.call_source,
        le.source_url,
        le.case_number,
        le.dispatched_at,
        le.arrived_at,
        le.cleared_at,
        le.officer,
        pl.normalized_address,
        pl.kind AS address_kind,
        pl.coordinate_precision,
        pl.street,
        pl.lat,
        pl.lng,
        pl.names_person AS flagged,
        le.category
    FROM public_log_entries le
    JOIN public_locations pl
        ON le.raw_location = pl.raw_address
    WHERE le.parse_error = false
      AND le.log_date >= $1
      -- A flagged location has no pin, and stays until its street's pin takes it in.
      AND (pl.names_person OR (pl.lat IS NOT NULL AND pl.lng IS NOT NULL))
),
own AS (
    SELECT * FROM entries WHERE NOT flagged
),
groups AS (
    SELECT
        normalized_address,
        lat,
        lng,
        -- The most common public spelling of the place, the first in sort order on a tie.
        MODE() WITHIN GROUP (ORDER BY location) AS raw_address,
        CASE
            WHEN normalized_address IS NULL
                OR strpos(normalized_address, ', ') > 0
                THEN 'place'
            WHEN bool_or(address_kind IN ('intersection', 'highway')) THEN 'road'
            WHEN normalized_address ~ '^\d' THEN 'place'
            ELSE 'road'
        END AS kind,
        -- A pin is approximate when any spelling of it sits on its street's point.
        CASE
            WHEN bool_or(coordinate_precision = 'approximate') THEN 'approximate'
            ELSE 'exact'
        END AS coordinate_precision,
        MODE() WITHIN GROUP (ORDER BY street) AS street,
        bool_or(address_kind IN ('intersection', 'highway')) AS junction
    FROM own
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
own_tagged AS (
    SELECT own.*, pins.id AS own_pin_id, pins.kind AS own_kind
    FROM own
    JOIN pins
        ON own.normalized_address IS NOT DISTINCT FROM pins.normalized_address
       AND own.lat = pins.lat
       AND own.lng = pins.lng
),
own_counted AS (
    -- Each pin's own entries, before anything is folded, so which pin is a street's never
    -- depends on the entries moved onto it.
    SELECT
        own_pin_id AS pin_id,
        COUNT(*) FILTER (WHERE category <> 'traffic' OR own_kind = 'road') AS count,
        COUNT(*) FILTER (WHERE category = 'traffic') AS traffic
    FROM own_tagged
    GROUP BY own_pin_id
),
street_pins AS (
    -- The pin of a street: the bare street with that street, the busiest by its own calls
    -- if there are several, and the lowest id on a tie. An intersection has a first street
    -- too, but is not it. A place on a street's point, a flagged location, and the traffic
    -- at a place all hang on this one pin, so there is one rule for them.
    SELECT DISTINCT ON (road.street) road.street, road.id AS pin_id
    FROM pins road
    JOIN own_counted ON own_counted.pin_id = road.id
    WHERE road.kind = 'road'
      AND NOT road.junction
      AND road.street IS NOT NULL
    ORDER BY road.street, own_counted.count DESC, road.id
),
tagged AS (
    -- Where each entry is counted. The street pin of every street is chosen above, from
    -- the pins' own entries, so folding entries onto it cannot change which pin it is.
    -- The traffic at a place is counted on its street's pin as a road call, because it
    -- happened on the road. With no street pin it stays on the place, counted nowhere.
    SELECT
        own_tagged.*,
        COALESCE(street_pins.pin_id, own_tagged.own_pin_id) AS pin_id,
        CASE
            WHEN street_pins.pin_id IS NOT NULL THEN 'road'
            ELSE own_tagged.own_kind
        END AS kind
    FROM own_tagged
    LEFT JOIN street_pins
        ON own_tagged.own_kind = 'place'
       AND own_tagged.category = 'traffic'
       AND street_pins.street = own_tagged.street
    UNION ALL
    -- A flagged entry is counted on its street's pin as a road call. With no street pin it
    -- is in no place card, and the town totals still hold it.
    SELECT
        entries.*,
        NULL::text AS own_pin_id,
        NULL::text AS own_kind,
        street_pins.pin_id,
        'road' AS kind
    FROM entries
    JOIN street_pins ON street_pins.street = entries.street
    WHERE entries.flagged
),
counted AS (
    -- Every pin has a row, even one whose entries all folded onto a street.
    SELECT
        pins.id AS pin_id,
        COUNT(*) FILTER (WHERE tagged.category = 'premises') AS premises,
        COUNT(*) FILTER (WHERE tagged.category = 'traffic')  AS traffic,
        COUNT(*) FILTER (WHERE tagged.category = 'alarms')   AS alarms,
        COUNT(*) FILTER (WHERE tagged.category = 'checks')   AS checks,
        COUNT(*) FILTER (WHERE tagged.category = 'admin')    AS admin,
        COUNT(*) FILTER (
            WHERE tagged.category <> 'traffic' OR tagged.kind = 'road'
        ) AS count
    FROM pins
    LEFT JOIN tagged ON tagged.pin_id = pins.id
    GROUP BY pins.id
),
links AS (
    -- A place on a street's point has no spot of its own. It hangs on its street's card.
    SELECT place.id AS pin_id, street_pins.pin_id AS street_id
    FROM pins place
    JOIN street_pins ON street_pins.street = place.street
    WHERE place.kind = 'place'
      AND place.coordinate_precision = 'approximate'
)
SELECT
    pins.id,
    pins.kind,
    pins.raw_address,
    pins.normalized_address,
    counted.count,
    -- The traffic that is counted nowhere, or on a road, all of it. For a place that is the
    -- traffic with no street pin to fold onto, usually none. A road's is already in its count.
    counted.traffic AS traffic_count,
    -- The traffic at a place, folded or not, for the card's "stops nearby" line. It is never
    -- added to a count, a total or an activity entry.
    CASE WHEN pins.kind = 'road' THEN 0 ELSE own_counted.traffic END AS nearby_traffic,
    pins.lat,
    pins.lng,
    pins.coordinate_precision AS precision,
    links.street_id,
    links.street_id IS NOT NULL AS hidden,
    jsonb_build_object(
        'name', COALESCE(pins.normalized_address, pins.raw_address),
        'kind', pins.kind,
        'lat', pins.lat,
        'lng', pins.lng,
        'count', counted.count,
        'categories', jsonb_build_object(
            'premises', counted.premises,
            'traffic', CASE WHEN pins.kind = 'road' THEN counted.traffic ELSE own_counted.traffic END,
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
                  -- "Other" is every type with no plain name. The card adds it as its
                  -- last row, from what the listed rows leave out.
                  AND incident_type <> 'Other'
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
                'raw_incident_type', raw_incident_type,
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
                SELECT reported_at, incident_type, raw_incident_type, disposition,
                       call_source, category, source_url, case_number, dispatched_at,
                       arrived_at, cleared_at, officer
                FROM tagged
                WHERE pin_id = pins.id
                  AND (kind = 'road' OR category <> 'traffic')
                ORDER BY reported_at DESC NULLS LAST, source_url
                LIMIT 10
            ) latest
        )
    )::text AS card,
    -- Every entry of the pin, for activity.json, in log order. An entry with no report time
    -- falls back to its log day, so it still counts toward the day and the week.
    (
        SELECT COALESCE(jsonb_agg(jsonb_build_array(
            COALESCE(reported_at, log_date::timestamp),
            category,
            incident_type,
            disposition,
            call_source,
            officer,
            dispatched_at,
            arrived_at,
            cleared_at
        ) ORDER BY COALESCE(reported_at, log_date::timestamp), source_url, case_number), '[]')
        FROM tagged
        WHERE pin_id = pins.id
    )::text AS entries,
    -- What stats.json counts, from the entries that are on a pin: the report time, which is
    -- null when the log had none, and the type.
    (
        SELECT COALESCE(jsonb_agg(jsonb_build_array(reported_at, incident_type)), '[]')
        FROM tagged
        WHERE pin_id = pins.id
    )::text AS stat_entries
FROM pins
JOIN counted ON counted.pin_id = pins.id
JOIN own_counted ON own_counted.pin_id = pins.id
LEFT JOIN links ON links.pin_id = pins.id
ORDER BY counted.count DESC, counted.traffic DESC, pins.normalized_address, pins.id
