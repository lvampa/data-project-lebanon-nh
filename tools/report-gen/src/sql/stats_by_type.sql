-- The twenty busiest plain type names, then "Other", which is every type with no plain
-- name. "Other" is last whatever its count.
WITH counted AS (
    SELECT incident_type, COUNT(*) AS count
    FROM public_log_entries
    WHERE parse_error = false
      AND log_date >= $1
    GROUP BY incident_type
)
SELECT incident_type, count
FROM (
    (SELECT * FROM counted
     WHERE incident_type <> 'Other'
     ORDER BY count DESC, incident_type
     LIMIT 20)
    UNION ALL
    SELECT * FROM counted WHERE incident_type = 'Other'
) listed
ORDER BY incident_type = 'Other', count DESC, incident_type
