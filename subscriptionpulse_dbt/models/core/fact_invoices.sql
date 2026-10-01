-- Grain: one row per invoice.
-- is_paid distinguishes collected revenue from other invoice statuses.

select
    invoice_id,
    account_id,
    invoice_date,
    amount,
    status,
    payment_method,
    (status = 'paid') as is_paid
from {{ ref('stg_invoices') }}
