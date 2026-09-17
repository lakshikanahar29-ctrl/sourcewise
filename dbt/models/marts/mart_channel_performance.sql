-- Channel x model x month (month the deal was created). Spend joined for paid channels.
with credit as (
    select model, channel, date_trunc('month', deal_created_at)::date as month,
           sum(credit)                                       as credited_deals,
           sum(credit) filter (where is_won)                 as credited_wins,
           sum(credited_pipeline)                            as pipeline_usd,
           sum(credited_won_revenue)                         as won_revenue_usd
    from {{ ref('fct_attribution') }}
    group by 1, 2, 3
),
spend as (
    select channel, date_trunc('month', spend_date)::date as month, sum(spend_usd) as spend_usd, sum(clicks) as clicks
    from {{ ref('stg_ads__spend_daily') }}
    group by 1, 2
)
select c.model, c.channel, dc.channel_group, c.month,
       round(c.credited_deals, 3)   as credited_deals,
       round(coalesce(c.credited_wins, 0), 3) as credited_wins,
       round(c.pipeline_usd, 2)     as pipeline_usd,
       round(c.won_revenue_usd, 2)  as won_revenue_usd,
       s.spend_usd,
       s.clicks
from credit c
left join spend s on s.channel = c.channel and s.month = c.month
left join {{ ref('dim_channel') }} dc on dc.channel = c.channel
