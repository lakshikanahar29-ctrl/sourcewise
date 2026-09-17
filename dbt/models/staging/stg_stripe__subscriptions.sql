select
    id                                                    as subscription_id,
    lower(customer_domain)                                as domain,
    status,
    start_date::date                                      as start_date,
    current_mrr_cents::bigint / 100.0                     as current_mrr_usd
from {{ source('raw', 'stripe_subscriptions') }}
