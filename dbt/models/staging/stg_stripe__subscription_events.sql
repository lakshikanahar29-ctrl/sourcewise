select
    subscription_id,
    event_type,
    mrr_delta_cents::bigint / 100.0                       as mrr_delta_usd,
    occurred_on::date                                     as occurred_on
from {{ source('raw', 'stripe_subscription_events') }}
