{{ config(tags=['week05']) }}

select column_name
from information_schema.columns
where table_schema = '{{ target.schema }}'
  and table_name = 'agent_tool_input_view'
  and column_name in ('contact_email', 'subject', 'body', 'body_preview', 'customer_id')
