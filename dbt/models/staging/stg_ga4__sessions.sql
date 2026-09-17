select
    session_id,
    client_id,
    session_start::timestamptz                            as started_at,
    nullif(lower(utm_source), '')                         as utm_source,
    nullif(lower(utm_medium), '')                         as utm_medium,
    nullif(utm_campaign, '')                              as utm_campaign,
    nullif(lower(referrer), '')                           as referrer,
    landing_page,
    {{ classify_web_channel('lower(utm_source)', 'lower(utm_medium)', 'lower(referrer)') }} as channel
from {{ source('raw', 'ga4_sessions') }}
