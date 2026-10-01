-- Grain: one row per usage event.
-- Append-only fact table containing product activity.

select
    event_id,
    account_id,
    event_type,
    event_time,
    cast(event_time as date) as event_date
from {{ ref('stg_usage_events') }}
