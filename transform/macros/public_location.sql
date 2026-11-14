{#
  The one place that works out what the public sees of a location (6.11, 11.6 to 11.9).

  kind 'address':  built only from `street`, the matched street from the street list,
                   never from the AI's address text, so no house number, unit or note
                   can reach the site. A leading house number of 100 or more gives
                   "<n00> block of <Street>"; under 100, or none, gives "<Street>".
                   No street gives nothing. Coordinates are rounded to 3 places.
  other kinds:     the normalized address and coordinates as stored (11.7); the data
                   check assert_public_non_address_has_no_house_number guards them.
  no kind:         no normalization yet, so nothing public (11.9).

  `street` is canonical upper case ("MAIN ST"); initcap shows it as "Main St".
#}

{% macro _house_number(normalized_address) -%}
    (regexp_match(btrim({{ normalized_address }}), '^(\d+)[A-Za-z]?\s'))[1]::bigint
{%- endmacro %}

{% macro public_location(kind, normalized_address, street) -%}
    case
        when {{ kind }} is null then null
        when {{ kind }} = 'address' then
            case
                when {{ street }} is null then null
                when coalesce({{ _house_number(normalized_address) }}, 0) < 100
                    then initcap({{ street }})
                else
                    ({{ _house_number(normalized_address) }} / 100 * 100)::text
                    || ' block of ' || initcap({{ street }})
            end
        else {{ normalized_address }}
    end
{%- endmacro %}

{% macro public_coordinate(kind, coordinate, street) -%}
    case
        when {{ kind }} is null then null
        when {{ kind }} = 'address' and {{ street }} is null then null
        when {{ kind }} = 'address' then round(({{ coordinate }})::numeric, 3)::float8
        else {{ coordinate }}
    end
{%- endmacro %}
