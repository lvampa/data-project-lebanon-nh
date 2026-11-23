SELECT EXTRACT(DOW FROM reported_at)::FLOAT8 AS dow, COUNT(*) AS count
FROM public_log_entries
WHERE parse_error = false
  AND reported_at IS NOT NULL
  AND log_date >= $1
GROUP BY dow
ORDER BY dow
