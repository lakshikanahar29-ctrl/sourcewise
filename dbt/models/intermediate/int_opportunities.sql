-- One row per deal. Won/lost comes from the current stage, not from history, because
-- some deals were marked lost and then re-opened and won (see metric changelog).
with hist as (
    select deal_id,
           max(changed_at) filter (where stage = 'closedwon')  as won_at,
           max(changed_at) filter (where stage = 'closedlost') as last_lost_at,
           count(*) filter (where stage = 'closedlost')        as times_marked_lost
    from {{ ref('stg_hubspot__deal_stage_history') }}
    group by deal_id
)
select
    d.deal_id,
    d.deal_name,
    d.company_id,
    co.company_name,
    co.domain,
    co.industry,
    co.size_band,
    d.contact_id,
    d.contact_id is null                                   as is_missing_contact,
    d.amount,
    d.created_at,
    d.current_stage,
    d.is_closed,
    d.is_won,
    case when d.is_won then h.won_at when d.is_closed then h.last_lost_at end as closed_at,
    case when d.is_closed then extract(day from (case when d.is_won then h.won_at else h.last_lost_at end) - d.created_at)::int end
                                                           as cycle_days,
    d.is_won and h.times_marked_lost > 0                   as was_reopened
from {{ ref('stg_hubspot__deals') }} d
left join hist h using (deal_id)
left join {{ ref('stg_hubspot__companies') }} co using (company_id)
