{#
  The only model that reads the planted ground truth. Compares each attribution model's share of
  won revenue to each channel's true incremental share, for the channels the generator simulated.
  organic_social / other do not exist in the truth: they are pure misclassification (untagged ads).
#}
with truth as (
    select channel, greatest(expected_incremental_revenue::numeric, 0) as incremental
    from {{ source('truth', 'channel_incrementality') }}
),
truth_share as (
    select channel, incremental / sum(incremental) over () as true_share from truth
),
model_share as (
    select model, channel, share_of_won_revenue
    from {{ ref('mart_channel_summary') }}
),
models as (select distinct model from model_share),
grid as (
    select m.model, t.channel, t.true_share, coalesce(ms.share_of_won_revenue, 0) as model_share
    from models m cross join truth_share t
    left join model_share ms on ms.model = m.model and ms.channel = t.channel
),
scored as (
    select model, channel, true_share, model_share,
           avg(abs(model_share - true_share)) over (partition by model) as model_mean_abs_error
    from grid
)
select model, channel,
       round(true_share, 4)                   as true_share,
       round(model_share, 4)                  as model_share,
       round(model_share - true_share, 4)     as error,
       round(model_mean_abs_error, 4)         as model_mean_abs_error,
       dense_rank() over (order by round(model_mean_abs_error, 4)) as model_rank
from scored
