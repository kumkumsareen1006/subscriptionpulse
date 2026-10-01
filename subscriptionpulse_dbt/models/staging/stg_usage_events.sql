select
    event_id,
    account_id,
    lower(trim(event_type)) as event_type,
    event_time,
    updated_at
from {{ source('raw', 'usage_events') }}
