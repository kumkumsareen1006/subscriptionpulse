-- Custom test #3 (from the Day 1 brief): no two versions of the same
-- account should have overlapping valid_from/valid_to ranges. If
-- dbt snapshot is working correctly, this should always return 0 rows —
-- this test exists as a safety net proving that mechanism, not because
-- it's expected to ever actually catch anything.
select
    account_id,
    valid_from,
    valid_to,
    lead(valid_from) over (partition by account_id order by valid_from) as next_valid_from
from {{ ref('dim_accounts') }}
qualify next_valid_from < valid_to
