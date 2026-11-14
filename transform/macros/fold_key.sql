{#
  The case and spacing fold the normalization job groups incident types by (5.3).
  Locations are grouped in Python by shared/locations canonical_address, and every raw
  value still gets its own lookup row, so this fold only has to match rows to entries.
#}
{% macro fold_key(expr) -%}
    lower(regexp_replace(btrim({{ expr }}), '\s+', ' ', 'g'))
{%- endmacro %}
