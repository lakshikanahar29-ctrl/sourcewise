-- Sales cycle and win rate by the channel that started the relationship.
select coalesce(first_touch_channel, 'unattributed') as first_touch_channel,
       count(*)                                                   as opps,
       count(*) filter (where is_closed)                          as closed_opps,
       count(*) filter (where is_won)                             as won_opps,
       round(count(*) filter (where is_won)::numeric / nullif(count(*) filter (where is_closed), 0), 3) as win_rate,
       round(avg(amount) filter (where is_won), 0)                as avg_won_deal_usd,
       percentile_cont(0.5) within group (order by cycle_days) filter (where is_won) as median_cycle_days_won
from {{ ref('fct_opportunities') }}
group by 1
