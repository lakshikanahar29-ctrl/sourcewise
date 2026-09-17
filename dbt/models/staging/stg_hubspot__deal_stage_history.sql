select
    deal_id::bigint                                       as deal_id,
    dealstage                                             as stage,
    changed_at::timestamptz                               as changed_at
from {{ source('raw', 'hubspot_deal_stage_history') }}
