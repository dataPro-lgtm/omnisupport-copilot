select
    created_date as activity_date,
    coalesce(product_line, 'unknown') as product_line,
    coalesce(priority, 'unknown') as priority,
    coalesce(org_id, 'unknown') as org_id,
    coalesce(category, 'unknown') as category,
    count(*)::integer as ticket_count,
    sum(case when is_open then 1 else 0 end)::integer as open_ticket_count,
    sum(case when is_p1 then 1 else 0 end)::integer as p1_ticket_count,
    sum(case when sla_breached then 1 else 0 end)::integer as sla_breach_count,
    sum(case when is_escalated then 1 else 0 end)::integer as escalation_count,
    sum(case when is_resolved then 1 else 0 end)::integer as resolved_ticket_count,
    sum(case when is_first_resolution_proxy then 1 else 0 end)::integer as first_resolution_count,
    avg(backlog_age_days)::numeric(12, 4) as avg_backlog_age_days,
    avg(first_response_minutes)::numeric(12, 4) as avg_first_response_minutes,
    avg(handle_time_minutes)::numeric(12, 4) as avg_handle_time_minutes,
    (
        sum(case when is_escalated then 1 else 0 end)::numeric
        / nullif(count(*)::numeric, 0)
    )::numeric(12, 4) as escalation_rate,
    (
        sum(case when sla_breached then 1 else 0 end)::numeric
        / nullif(count(*)::numeric, 0)
    )::numeric(12, 4) as sla_breach_rate,
    (
        sum(case when is_first_resolution_proxy then 1 else 0 end)::numeric
        / nullif(sum(case when is_resolved then 1 else 0 end)::numeric, 0)
    )::numeric(12, 4) as first_resolution_rate
from {{ ref('int_support_cases') }}
group by 1, 2, 3, 4, 5
