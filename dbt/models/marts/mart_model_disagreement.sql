-- How much each channel's share of won revenue swings depending on the model you pick.
with s as (
    select channel, model, share_of_won_revenue from {{ ref('mart_channel_summary') }}
),
p as (
    select channel,
           max(share_of_won_revenue) filter (where model = 'first_touch')     as first_touch,
           max(share_of_won_revenue) filter (where model = 'last_non_direct') as last_non_direct,
           max(share_of_won_revenue) filter (where model = 'linear')          as linear,
           max(share_of_won_revenue) filter (where model = 'w_shaped')        as w_shaped,
           max(share_of_won_revenue) filter (where model = 'time_decay')      as time_decay
    from s group by channel
)
select p.*,
       greatest(coalesce(first_touch,0), coalesce(last_non_direct,0), coalesce(linear,0), coalesce(w_shaped,0), coalesce(time_decay,0))
     - least(coalesce(first_touch,0), coalesce(last_non_direct,0), coalesce(linear,0), coalesce(w_shaped,0), coalesce(time_decay,0)) as swing,
       rank() over (order by greatest(coalesce(first_touch,0), coalesce(last_non_direct,0), coalesce(linear,0), coalesce(w_shaped,0), coalesce(time_decay,0))
                         - least(coalesce(first_touch,0), coalesce(last_non_direct,0), coalesce(linear,0), coalesce(w_shaped,0), coalesce(time_decay,0)) desc) as swing_rank
from p
