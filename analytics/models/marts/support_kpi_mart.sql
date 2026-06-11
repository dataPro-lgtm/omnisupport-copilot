with daily as (
    select
        activity_date as metric_date,
        product_line,
        priority,
        org_id,
        category,
        ticket_count,
        open_ticket_count,
        p1_ticket_count,
        sla_breach_count,
        escalation_count,
        resolved_ticket_count,
        first_resolution_count,
        avg_backlog_age_days,
        avg_first_response_minutes,
        avg_handle_time_minutes,
        escalation_rate,
        sla_breach_rate,
        first_resolution_rate
    from {{ ref('int_ticket_activity_daily') }}
),

metric_rows as (
    select
        daily.metric_date,
        metrics.metric_name,
        daily.product_line,
        daily.priority,
        daily.org_id,
        daily.category,
        metrics.metric_value,
        daily.ticket_count,
        daily.open_ticket_count,
        daily.p1_ticket_count,
        daily.sla_breach_count,
        daily.escalation_count,
        daily.resolved_ticket_count,
        daily.first_resolution_count,
        daily.avg_backlog_age_days,
        daily.avg_first_response_minutes,
        daily.avg_handle_time_minutes,
        daily.escalation_rate,
        daily.sla_breach_rate,
        daily.first_resolution_rate
    from daily
    cross join lateral (
        values
            ('ticket_count', daily.ticket_count::numeric),
            ('open_ticket_count', daily.open_ticket_count::numeric),
            ('p1_ticket_count', daily.p1_ticket_count::numeric),
            ('sla_breach_count', daily.sla_breach_count::numeric),
            ('escalation_count', daily.escalation_count::numeric),
            ('avg_backlog_age_days', daily.avg_backlog_age_days::numeric),
            ('avg_first_response_minutes', daily.avg_first_response_minutes::numeric),
            ('avg_handle_time_minutes', daily.avg_handle_time_minutes::numeric),
            ('first_resolution_rate', daily.first_resolution_rate::numeric),
            ('escalation_rate', daily.escalation_rate::numeric),
            ('sla_breach_rate', daily.sla_breach_rate::numeric)
    ) as metrics(metric_name, metric_value)
    where metrics.metric_value is not null
)

select
    metric_date,
    metric_name,
    product_line,
    priority,
    org_id,
    category,
    metric_value,
    ticket_count,
    open_ticket_count,
    p1_ticket_count,
    sla_breach_count,
    escalation_count,
    resolved_ticket_count,
    first_resolution_count,
    avg_backlog_age_days,
    avg_first_response_minutes,
    avg_handle_time_minutes,
    escalation_rate,
    sla_breach_rate,
    first_resolution_rate,
    '{{ var("week05_data_release_id") }}' as data_release_id,
    current_timestamp as generated_at
from metric_rows
