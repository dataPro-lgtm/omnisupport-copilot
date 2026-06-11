{{ config(tags=['week05']) }}

select *
from {{ ref('support_kpi_mart') }}
where metric_name in (
    'first_resolution_rate',
    'escalation_rate',
    'sla_breach_rate'
)
and (metric_value < 0 or metric_value > 1)
