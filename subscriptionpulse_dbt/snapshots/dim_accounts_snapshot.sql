{% snapshot dim_accounts_snapshot %}

{{
    config(
        target_schema='snapshots',
        unique_key='account_id',
        strategy='timestamp',
        updated_at='updated_at',
    )
}}

-- Type 2 snapshot tracking account changes using updated_at.
-- Previous versions are retained with dbt_valid_to marking their validity end.
select
    account_id,
    workspace_name,
    contact_email,
    signup_date,
    plan_tier,
    status,
    updated_at
from {{ ref('stg_accounts') }}

{% endsnapshot %}
