SELECT incident_type, COUNT(*) AS count
FROM log_entries
WHERE parse_error = false
  AND incident_type IS NOT NULL
  AND log_date >= $1
GROUP BY incident_type
ORDER BY count DESC
LIMIT 20
