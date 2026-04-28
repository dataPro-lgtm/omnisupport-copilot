select
    customer_id,
    org_id,
    org_name,
    lower(sla_tier::text) as sla_tier,
    created_at,
    updated_at
from {{ source('omni_postgres', 'customer_dim') }}
