-- Standardize account attributes and retain the latest record per account.
-- raw.accounts is append-only, so updated accounts may have multiple versions.

select
    account_id,
    trim(workspace_name)       as workspace_name,
    lower(trim(contact_email)) as contact_email,
    signup_date,
    lower(trim(plan_tier))     as plan_tier,
    lower(trim(status))        as status,
    updated_at
from {{ source('raw', 'accounts') }}
qualify row_number() over (partition by account_id order by updated_at desc) = 1
