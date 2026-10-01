-- Custom test #1 (from the Day 1 brief). Passes when this returns 0 rows.
select *
from {{ ref('fact_invoices') }}
where amount < 0
