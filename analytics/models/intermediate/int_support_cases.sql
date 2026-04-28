with tickets as (
    select * from {{ ref('stg_tickets') }}
),

customers as (
    select * from {{ ref('stg_customers') }}
),

first_comments as (
    select
        ticket_id,
        min(created_at) as first_comment_at
    from {{ ref('stg_ticket_comments') }}
    group by ticket_id
),

joined as (
    select
        t.ticket_id,
        t.customer_id,
        t.org_id,
        c.org_name,
        t.status,
        t.priority,
        t.category,
        t.product_line,
        t.product_version,
        t.assignee_id,
        t.sla_tier,
        t.sla_due_at,
        t.created_at,
        t.created_date,
        t.updated_at,
        t.resolved_at,
        t.data_release_id,
        t.ingest_batch_id,
        t.schema_version,
        t.pii_level,
        t.pii_redacted,
        t.is_open,
        t.is_resolved,
        t.is_escalated,
        t.is_p1,
        t.sla_breached,
        fc.first_comment_at,
        case
            when fc.first_comment_at is not null
                then extract(epoch from (fc.first_comment_at - t.created_at)) / 60.0
            else null
        end as first_response_minutes,
        case
            when t.resolved_at is not null
                then extract(epoch from (t.resolved_at - t.created_at)) / 86400.0
            else extract(epoch from (current_timestamp - t.created_at)) / 86400.0
        end as backlog_age_days
    from tickets t
    left join customers c on t.customer_id = c.customer_id
    left join first_comments fc on t.ticket_id = fc.ticket_id
)

select * from joined
