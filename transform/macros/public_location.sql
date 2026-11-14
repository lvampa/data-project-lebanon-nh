{#
  The one place that works out what the public sees of a location (6.11, 11.6 to 11.9).

  kind 'address':  the leading house number is rounded down to the hundred and written
                   as "<n> block of <street>"; a number under 100 gives the street alone;
                   coordinates are rounded to 3 places, about 100 meters.
  other kinds:     the normalized address and coordinates as stored (11.7).
  no kind:         no normalization yet, so nothing public: the raw value may be a house
                   address (11.9).

  An address with no leading number (for example a bare street) is shown as stored.
  A trailing unit is dropped before the street is shown, so "12 Main St Unit 3" never
  publishes the unit.
  TODO(PR 4 task 11): keep the unit designators in step with shared/locations strip_unit.
#}

{% macro _address_parts(normalized_address) -%}
    regexp_match(
        regexp_replace(
            btrim({{ normalized_address }}),
            '\s+(unit|apt|apartment|suite|ste|#)\s*\S+$', '', 'i'
        ),
        '^(\d+)[A-Za-z]?\s+(.+)$'
    )
{%- endmacro %}

{% macro public_location(kind, normalized_address) -%}
    case
        when {{ kind }} is null then null
        when {{ kind }} = 'address'
            and ({{ _address_parts(normalized_address) }}) is not null
        then
            case
                when (({{ _address_parts(normalized_address) }})[1])::bigint < 100
                    then ({{ _address_parts(normalized_address) }})[2]
                else
                    ((({{ _address_parts(normalized_address) }})[1])::bigint / 100 * 100)::text
                    || ' block of '
                    || ({{ _address_parts(normalized_address) }})[2]
            end
        else {{ normalized_address }}
    end
{%- endmacro %}

{% macro public_coordinate(kind, coordinate) -%}
    case
        when {{ kind }} is null then null
        when {{ kind }} = 'address' then round(({{ coordinate }})::numeric, 3)::float8
        else {{ coordinate }}
    end
{%- endmacro %}
