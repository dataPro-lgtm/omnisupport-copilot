select
    comment_id,
    ticket_id,
    author_id,
    author_role,
    body_preview,
    created_at
from {{ source('omni_postgres', 'ticket_comment_fact') }}
