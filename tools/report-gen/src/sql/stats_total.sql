SELECT COUNT(*)
FROM log_entries
WHERE parse_error = false
  AND reported_at >= CAST($1 AS timestamp)
