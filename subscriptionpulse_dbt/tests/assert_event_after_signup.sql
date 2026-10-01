-- Custom test #2 (from the Day 1 brief): no usage event before its
-- account's signup date. signup_date never changes across SCD2 versions,
-- so stg_accounts (already deduplicated to one row per account) is enough
-- here — no need to depend on dim_accounts for this one.
select
    e.event_id,
    e.account_id,
    e.event_time,
    a.signup_date
from {{ ref('fact_usage_events') }} e
join {{ ref('stg_accounts') }} a using (account_id)
where e.event_time < a.signup_date
