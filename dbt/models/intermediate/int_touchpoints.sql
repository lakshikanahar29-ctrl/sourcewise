-- Every touch from every system, in one shape, tied to a person and their account.
with web as (
    select s.session_id                     as source_record_id,
           c.person_id,
           s.started_at                     as touched_at,
           s.channel,
           'web_session'                    as touch_type,
           'ga4'                            as source_system
    from {{ ref('stg_ga4__sessions') }} s
    join {{ ref('int_identity__client_map') }} c using (client_id)
),
email as (
    -- sends are not touches: the prospect did nothing. Clicks and replies are.
    select e.email_event_id, m.person_id, e.event_at, e.channel,
           'email_' || e.event_type, 'smartlead'
    from {{ ref('stg_smartlead__email_events') }} e
    join {{ ref('int_identity__email_map') }} m using (email)
    where e.event_type in ('click', 'reply')
),
signals as (
    -- Clay rows with no email are matched on name + company domain
    select s.signal_id, p.person_id, s.detected_at, 'signal_engine', 'signal_detected', 'clay'
    from {{ ref('stg_clay__signal_leads') }} s
    join {{ ref('int_identity__people') }} p
      on (s.email is not null and p.work_email = s.email)
      or (s.email is null and p.full_name_key = s.full_name_key and p.company_domain = s.company_domain)
),
bot as (
    select t.thread_id, m.person_id, t.bot_replied_at, 'reply_bot', 'bot_reply', 'reply_bot'
    from {{ ref('stg_reply_bot__threads') }} t
    join {{ ref('int_identity__email_map') }} m using (email)
    where t.bot_replied_at is not null
),
voice as (
    select v.call_id, m.person_id, v.called_at, 'voice_agent', 'voice_call', 'voice_agent'
    from {{ ref('stg_voice_agent__calls') }} v
    join {{ ref('int_identity__email_map') }} m using (email)
    where v.outcome <> 'no_answer'
),
unioned as (
    select * from web
    union all select * from email
    union all select * from signals
    union all select * from bot
    union all select * from voice
)
select
    {{ dbt_utils_md5(["u.source_system", "u.source_record_id"]) }} as touchpoint_id,
    u.source_record_id,
    u.person_id,
    p.company_id,
    u.touched_at,
    u.channel,
    u.touch_type,
    u.source_system
from unioned u
join {{ ref('int_identity__people') }} p using (person_id)
