SELECT COUNT(*)
FROM log_entries
WHERE parse_error = false
  AND log_date >= $1
