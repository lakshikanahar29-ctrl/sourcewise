select o.*,
       ft.channel as first_touch_channel,
       lt.channel as last_non_direct_channel
from {{ ref('int_opportunities') }} o
left join {{ ref('fct_attribution') }} ft on ft.deal_id = o.deal_id and ft.model = 'first_touch'
left join {{ ref('fct_attribution') }} lt on lt.deal_id = o.deal_id and lt.model = 'last_non_direct'
