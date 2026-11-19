SELECT EXTRACT(HOUR FROM reported_at)::INT AS hour, COUNT(*) AS count
FROM log_entries
WHERE parse_error = false
  AND reported_at IS NOT NULL
  AND log_date >= $1
GROUP BY hour
ORDER BY hour
