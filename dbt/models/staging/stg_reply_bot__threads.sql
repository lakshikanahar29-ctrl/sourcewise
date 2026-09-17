select
    {{ dbt_utils_md5(["lead_email", "inbound_at"]) }}     as thread_id,
    lower(trim(lead_email))                               as email,
    inbound_at::timestamptz                               as inbound_at,
    intent_label,
    bot_replied_at::timestamptz                           as bot_replied_at,
    handed_off_to_human::boolean                          as handed_off_to_human
from {{ source('raw', 'reply_bot_threads') }}
