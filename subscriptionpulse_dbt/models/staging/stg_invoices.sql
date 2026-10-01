select
    invoice_id,
    account_id,
    amount,
    invoice_date,
    lower(trim(payment_method)) as payment_method,
    lower(trim(status))         as status,
    updated_at
from {{ source('raw', 'invoices') }}
