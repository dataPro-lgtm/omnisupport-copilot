{{ config(materialized='view') }}

select
    metric_date,
    metric_name,
    product_line,
    priority,
    org_id,
    category,
    metric_value,
    data_release_id,
    generated_at
from {{ ref('support_kpi_mart') }}
where metric_name in (
    'ticket_count',
    'open_ticket_count',
    'p1_ticket_count',
    'sla_breach_count',
    'escalation_count',
    'avg_backlog_age_days',
    'avg_first_response_minutes',
    'avg_handle_time_minutes',
    'first_resolution_rate',
    'escalation_rate',
    'sla_breach_rate'
)
