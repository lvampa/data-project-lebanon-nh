SELECT case_number, reported_at, call_source, incident_type,
       disposition, location, officer, reference_number, source_url
FROM public_log_entries
WHERE parse_error = false
  AND log_date >= $1
ORDER BY reported_at DESC NULLS LAST
LIMIT $2
