SELECT case_number, reported_at, call_source, incident_type,
       disposition, location, officer, reference_number, source_url
FROM log_entries
WHERE parse_error = false
  AND reported_at >= CAST($1 AS timestamp)
ORDER BY reported_at DESC NULLS LAST
LIMIT $2
