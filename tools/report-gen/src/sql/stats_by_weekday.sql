SELECT EXTRACT(DOW FROM reported_at)::FLOAT8 AS dow, COUNT(*) AS count
FROM log_entries
WHERE parse_error = false
  AND reported_at >= CAST($1 AS timestamp)
GROUP BY dow
ORDER BY dow
