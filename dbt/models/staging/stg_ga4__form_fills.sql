select
    session_id,
    client_id,
    lower(trim(email))                                    as email,
    form_name,
    submitted_at::timestamptz                             as submitted_at
from {{ source('raw', 'ga4_form_fills') }}
