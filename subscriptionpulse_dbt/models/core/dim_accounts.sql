-- Grain: one row per account version.
-- Type 2 slowly changing dimension preserving plan and status history.
-- Historical versioning is managed by the dim_accounts_snapshot dbt snapshot.

select
    account_id,
    workspace_name,
    contact_email,
    signup_date,
    plan_tier,
    status,
    dbt_valid_from as valid_from,
    dbt_valid_to as valid_to,
    (dbt_valid_to is null) as is_current
from {{ ref('dim_accounts_snapshot') }}
