select
    change_id,
    account_id,
    lower(trim(old_plan)) as old_plan,
    lower(trim(new_plan)) as new_plan,
    change_date,
    updated_at
from {{ source('raw', 'subscription_changes') }}
