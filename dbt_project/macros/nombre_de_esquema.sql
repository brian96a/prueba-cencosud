{# Usa el esquema tal cual (silver, gold) en vez de main_silver, main_gold #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name if custom_schema_name is not none else target.schema }}
{%- endmacro %}
