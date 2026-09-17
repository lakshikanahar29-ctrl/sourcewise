{# Stable surrogate key from several columns (small stand-in for dbt_utils.generate_surrogate_key). #}
{% macro dbt_utils_md5(cols) -%}
md5({% for c in cols %}coalesce({{ c }}::text, '') {% if not loop.last %}|| '|' || {% endif %}{% endfor %})
{%- endmacro %}
