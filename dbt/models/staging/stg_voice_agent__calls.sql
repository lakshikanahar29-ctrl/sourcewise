select
    call_id,
    lower(trim(lead_email))                               as email,
    -- the voice platform exports local India time with no offset
    (called_at_ist::timestamp at time zone 'Asia/Kolkata') as called_at,
    duration_sec::int                                     as duration_sec,
    outcome
from {{ source('raw', 'voice_agent_calls') }}
