-- Three ad platforms, three export shapes, one table.
select date::date as spend_date, 'linkedin_ads' as channel, campaign_name,
       clicks::int as clicks, cost_in_usd::numeric(12, 2) as spend_usd
from {{ source('raw', 'linkedin_ads_daily') }}
union all
select segments_date::date, 'google_ads', campaign_name,
       metrics_clicks::int, round(metrics_cost_micros::bigint / 1000000.0, 2)   -- Google reports micros
from {{ source('raw', 'google_ads_daily') }}
union all
select day::date, 'retargeting_ads', campaign,
       clicks::int, spend::numeric(12, 2)
from {{ source('raw', 'adroll_daily') }}
