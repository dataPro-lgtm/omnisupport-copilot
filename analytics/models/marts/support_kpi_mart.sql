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
        avg_backlog_age_days,
        avg_first_response_minutes
    from {{ ref('int_ticket_activity_daily') }}
),

metric_rows as (
    select
        metric_date,
        'ticket_count' as metric_name,
        product_line,
        priority,
        org_id,
        category,
        ticket_count::numeric as metric_value,
        ticket_count,
        open_ticket_count,
        p1_ticket_count,
        sla_breach_count,
        escalation_count,
        avg_backlog_age_days,
        avg_first_response_minutes
    from daily

    union all

    select
        metric_date,
        'open_ticket_count' as metric_name,
        product_line,
        priority,
        org_id,
        category,
        open_ticket_count::numeric as metric_value,
        ticket_count,
        open_ticket_count,
        p1_ticket_count,
        sla_breach_count,
        escalation_count,
        avg_backlog_age_days,
        avg_first_response_minutes
    from daily

    union all

    select
        metric_date,
        'p1_ticket_count' as metric_name,
        product_line,
        priority,
        org_id,
        category,
        p1_ticket_count::numeric as metric_value,
        ticket_count,
        open_ticket_count,
        p1_ticket_count,
        sla_breach_count,
        escalation_count,
        avg_backlog_age_days,
        avg_first_response_minutes
    from daily

    union all

    select
        metric_date,
        'sla_breach_count' as metric_name,
        product_line,
        priority,
        org_id,
        category,
        sla_breach_count::numeric as metric_value,
        ticket_count,
        open_ticket_count,
        p1_ticket_count,
        sla_breach_count,
        escalation_count,
        avg_backlog_age_days,
        avg_first_response_minutes
    from daily

    union all

    select
        metric_date,
        'escalation_count' as metric_name,
        product_line,
        priority,
        org_id,
        category,
        escalation_count::numeric as metric_value,
        ticket_count,
        open_ticket_count,
        p1_ticket_count,
        sla_breach_count,
        escalation_count,
        avg_backlog_age_days,
        avg_first_response_minutes
    from daily

    union all

    select
        metric_date,
        'avg_backlog_age_days' as metric_name,
        product_line,
        priority,
        org_id,
        category,
        avg_backlog_age_days::numeric as metric_value,
        ticket_count,
        open_ticket_count,
        p1_ticket_count,
        sla_breach_count,
        escalation_count,
        avg_backlog_age_days,
        avg_first_response_minutes
    from daily
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
    avg_backlog_age_days,
    avg_first_response_minutes,
    '{{ var("week05_data_release_id") }}' as data_release_id,
    current_timestamp as generated_at
from metric_rows
