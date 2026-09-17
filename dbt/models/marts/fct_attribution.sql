{#
  Long format: one row per (deal, model, touch). Adding a model = more rows, no schema change.
  Every deal gets exactly 1.0 credit per model. Deals with no touch in the window get a single
  'unattributed' row so revenue always reconciles.
#}
{% set anchor = var('w_shaped_anchor_weight') %}
{% set half_life = var('time_decay_half_life_days') %}
with t as (
    select w.*,
           max(touch_number) filter (where channel not in ('direct', 'other')) over (partition by deal_id) as last_non_direct_number,
           max(touch_number) filter (where lead_at is not null and touched_at <= lead_at) over (partition by deal_id) as lead_touch_number
    from {{ ref('int_deal_touch_window') }} w
),
weights as (
    select t.*,
        (touch_number = 1)::int                                                    as w_first,
        (touch_number = coalesce(last_non_direct_number, touch_count))::int        as w_last_non_direct,
        1.0 / touch_count                                                          as w_linear,
        {{ anchor }} * (touch_number = 1)::int
          + {{ anchor }} * (touch_number = coalesce(lead_touch_number, 1))::int
          + {{ anchor }} * (touch_number = touch_count)::int
          + case when touch_number not in (1, coalesce(lead_touch_number, 1), touch_count)
                 then (1 - 3 * {{ anchor }}) / nullif(touch_count - (case when touch_count >= 3 then 3 else touch_count end), 0)
                 else 0 end                                                        as w_w_raw,
        power(0.5, days_before_deal / {{ half_life }})                             as w_decay_raw
    from t
),
normalized as (
    select *,
        w_w_raw / sum(w_w_raw) over (partition by deal_id)         as w_w_shaped,
        w_decay_raw / sum(w_decay_raw) over (partition by deal_id) as w_time_decay
    from weights
),
long as (
    select deal_id, touchpoint_id, channel, touched_at, m.model, m.credit
    from normalized
    cross join lateral (values
        ('first_touch', w_first::numeric),
        ('last_non_direct', w_last_non_direct::numeric),
        ('linear', w_linear::numeric),
        ('w_shaped', w_w_shaped::numeric),
        ('time_decay', w_time_decay::numeric)
    ) as m(model, credit)
),
unattributed as (
    select o.deal_id, null::text as touchpoint_id, 'unattributed' as channel, null::timestamptz as touched_at, m.model, 1.0::numeric as credit
    from {{ ref('int_opportunities') }} o
    cross join (values ('first_touch'), ('last_non_direct'), ('linear'), ('w_shaped'), ('time_decay')) as m(model)
    where not exists (select 1 from {{ ref('int_deal_touch_window') }} w where w.deal_id = o.deal_id)
)
select
    {{ dbt_utils_md5(["a.deal_id", "a.model", "a.touchpoint_id"]) }} as attribution_id,
    a.deal_id, a.model, a.touchpoint_id, a.channel, a.touched_at,
    round(a.credit, 8)                                     as credit,
    o.created_at                                           as deal_created_at,
    o.closed_at,
    o.is_won,
    o.amount * a.credit                                    as credited_pipeline,
    case when o.is_won then o.amount * a.credit else 0 end as credited_won_revenue
from (select * from long where credit > 0 union all select * from unattributed) a
join {{ ref('int_opportunities') }} o using (deal_id)
