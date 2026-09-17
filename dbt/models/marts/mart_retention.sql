-- Net and gross revenue retention by first-touch channel of the deal that created the customer.
with subs as (
    select s.subscription_id, s.domain, s.start_date, s.current_mrr_usd,
           sum(e.mrr_delta_usd) filter (where e.event_type = 'new')         as starting_mrr,
           sum(e.mrr_delta_usd) filter (where e.event_type = 'expansion')   as expansion_mrr,
           -sum(e.mrr_delta_usd) filter (where e.event_type = 'contraction') as contraction_mrr,
           -sum(e.mrr_delta_usd) filter (where e.event_type = 'churn')      as churned_mrr
    from {{ ref('stg_stripe__subscriptions') }} s
    join {{ ref('stg_stripe__subscription_events') }} e using (subscription_id)
    group by 1, 2, 3, 4
),
won as (
    select distinct on (domain) domain, first_touch_channel
    from {{ ref('fct_opportunities') }} where is_won order by domain, closed_at desc
)
select case when grouping(coalesce(w.first_touch_channel, 'unattributed')) = 1 then 'all_customers'
            else coalesce(w.first_touch_channel, 'unattributed') end as first_touch_channel,
       count(*) as customers,
       round(sum(starting_mrr), 2) as starting_mrr_usd,
       round(sum(coalesce(expansion_mrr, 0)), 2) as expansion_mrr_usd,
       round(sum(coalesce(contraction_mrr, 0)), 2) as contraction_mrr_usd,
       round(sum(coalesce(churned_mrr, 0)), 2) as churned_mrr_usd,
       round(sum(current_mrr_usd), 2) as current_mrr_usd,
       round(sum(current_mrr_usd) / nullif(sum(starting_mrr), 0), 3) as net_revenue_retention,
       -- GRR ignores expansion: each customer counts at most their starting MRR
       round(sum(least(current_mrr_usd, starting_mrr)) / nullif(sum(starting_mrr), 0), 3) as gross_revenue_retention
from subs s
left join won w using (domain)
group by rollup (coalesce(w.first_touch_channel, 'unattributed'))
