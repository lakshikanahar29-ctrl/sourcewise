select
    hs_object_id::bigint                                  as deal_id,
    dealname                                              as deal_name,
    amount::numeric(12, 2)                                as amount,
    dealstage                                             as current_stage,
    createdate::timestamptz                               as created_at,
    closedate::timestamptz                                as close_date,
    hs_is_closed::boolean                                 as is_closed,
    dealstage = 'closedwon'                               as is_won,
    associatedcompanyid::bigint                           as company_id,
    associatedcontactid::bigint                           as contact_id
from {{ source('raw', 'hubspot_deals') }}
