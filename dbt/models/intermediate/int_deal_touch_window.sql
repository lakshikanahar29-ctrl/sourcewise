-- Account-based: every touch by anyone at the account in the lookback window before the deal was created.
with window_touches as (
    select o.deal_id, t.touchpoint_id, t.person_id, t.touched_at, t.channel, t.touch_type,
           extract(epoch from (o.created_at - t.touched_at)) / 86400.0 as days_before_deal
    from {{ ref('int_opportunities') }} o
    join {{ ref('int_touchpoints') }} t
      on t.company_id = o.company_id
     and t.touched_at <= o.created_at
     and t.touched_at >  o.created_at - interval '{{ var("lookback_days") }} days'
),
lead_moment as (
    -- first time anyone at the account became a lead inside the window
    select o.deal_id, min(l.lead_at) as lead_at
    from {{ ref('int_opportunities') }} o
    join {{ ref('int_identity__people') }} p on p.company_id = o.company_id
    join {{ ref('int_lead_events') }} l on l.person_id = p.person_id
     and l.lead_at <= o.created_at
     and l.lead_at >  o.created_at - interval '{{ var("lookback_days") }} days'
    group by o.deal_id
)
select
    w.*,
    row_number() over (partition by w.deal_id order by w.touched_at, w.touchpoint_id)      as touch_number,
    count(*)     over (partition by w.deal_id)                                              as touch_count,
    lm.lead_at
from window_touches w
left join lead_moment lm using (deal_id)
