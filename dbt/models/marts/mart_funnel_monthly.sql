with months as (
    select generate_series(date_trunc('month', (select min(started_at) from {{ ref('stg_ga4__sessions') }})),
                           date_trunc('month', (select max(started_at) from {{ ref('stg_ga4__sessions') }})),
                           interval '1 month')::date as month
),
sessions as (
    select date_trunc('month', s.started_at)::date as month, count(*) as sessions,
           count(*) filter (where c.client_id is not null) as identified_sessions
    from {{ ref('stg_ga4__sessions') }} s
    left join {{ ref('int_identity__client_map') }} c using (client_id)
    group by 1
),
leads as (
    select date_trunc('month', first_lead_at)::date as month, count(*) as new_leads
    from (select person_id, min(lead_at) as first_lead_at from {{ ref('int_lead_events') }} group by 1) x
    group by 1
),
meetings as (
    select date_trunc('month', called_at)::date as month, count(*) as voice_meetings_booked
    from {{ ref('stg_voice_agent__calls') }} where outcome = 'meeting_booked' group by 1
),
opps as (
    select date_trunc('month', created_at)::date as month, count(*) as opps_created, sum(amount) as pipeline_created_usd
    from {{ ref('int_opportunities') }} group by 1
),
wins as (
    select date_trunc('month', closed_at)::date as month,
           count(*) filter (where is_won) as deals_won,
           count(*) filter (where not is_won) as deals_lost,
           sum(amount) filter (where is_won) as won_revenue_usd
    from {{ ref('int_opportunities') }} where is_closed group by 1
)
select m.month,
       coalesce(s.sessions, 0) as sessions,
       coalesce(s.identified_sessions, 0) as identified_sessions,
       coalesce(l.new_leads, 0) as new_leads,
       coalesce(mt.voice_meetings_booked, 0) as voice_meetings_booked,
       coalesce(o.opps_created, 0) as opps_created,
       coalesce(o.pipeline_created_usd, 0) as pipeline_created_usd,
       coalesce(w.deals_won, 0) as deals_won,
       coalesce(w.deals_lost, 0) as deals_lost,
       coalesce(w.won_revenue_usd, 0) as won_revenue_usd,
       round(w.deals_won::numeric / nullif(w.deals_won + w.deals_lost, 0), 3) as win_rate
from months m
left join sessions s using (month)
left join leads l using (month)
left join meetings mt using (month)
left join opps o using (month)
left join wins w using (month)
order by m.month
