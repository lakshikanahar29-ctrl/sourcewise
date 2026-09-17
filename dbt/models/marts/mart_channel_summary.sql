-- All-time view per model and channel, with spend efficiency.
with perf as (
    select model, channel, channel_group,
           sum(credited_deals) as credited_deals, sum(credited_wins) as credited_wins,
           sum(pipeline_usd) as pipeline_usd, sum(won_revenue_usd) as won_revenue_usd
    from {{ ref('mart_channel_performance') }}
    group by 1, 2, 3
),
spend as (
    select channel, sum(spend_usd) as spend_usd from {{ ref('stg_ads__spend_daily') }} group by 1
)
select p.*,
       round(p.won_revenue_usd / sum(p.won_revenue_usd) over (partition by p.model), 4) as share_of_won_revenue,
       s.spend_usd,
       round(p.pipeline_usd / nullif(s.spend_usd, 0), 2)    as pipeline_per_dollar,
       round(s.spend_usd / nullif(p.credited_wins, 0), 0)   as cost_per_credited_win
from perf p
left join spend s using (channel)
