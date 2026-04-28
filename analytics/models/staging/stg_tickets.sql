with source as (
    select * from {{ source('omni_postgres', 'ticket_fact') }}
),

renamed as (
    select
        ticket_id,
        customer_id,
        org_id,
        lower(status::text) as status,
        lower(priority::text) as priority,
        category,
        product_line::text as product_line,
        product_version,
        subject,
        error_codes,
        asset_ids,
        assignee_id,
        lower(sla_tier::text) as sla_tier,
        sla_due_at,
        created_at,
        coalesce(updated_at, created_at) as updated_at,
        resolved_at,
        lower(pii_level::text) as pii_level,
        coalesce(pii_redacted, false) as pii_redacted,
        data_release_id,
        ingest_batch_id,
        schema_version,
        cast(created_at as date) as created_date,
        case when lower(status::text) in ('open', 'pending_customer', 'in_progress', 'escalated') then true else false end as is_open,
        case when lower(status::text) = 'resolved' then true else false end as is_resolved,
        case when lower(status::text) = 'escalated' then true else false end as is_escalated,
        case when lower(priority::text) in ('p1_critical', 'p1') then true else false end as is_p1,
        case
            when sla_due_at is null then false
            when coalesce(resolved_at, current_timestamp) > sla_due_at then true
            else false
        end as sla_breached
    from source
)

select * from renamed
