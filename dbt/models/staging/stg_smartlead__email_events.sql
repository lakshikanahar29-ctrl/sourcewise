select
    {{ dbt_utils_md5(["campaign_name", "lead_email", "event_type", "event_time"]) }} as email_event_id,
    campaign_name,
    -- signal-engine sequences were renamed from clay_signal_* to sig_* on 2026-02-01
    case when campaign_name like 'clay_signal_%' or campaign_name like 'sig_%'
         then 'signal_engine' else 'cold_email' end       as channel,
    lower(trim(lead_email))                               as email,
    event_type,
    event_time::timestamptz                               as event_at,
    nullif(reply_category, '')                            as reply_category
from {{ source('raw', 'smartlead_email_events') }}
