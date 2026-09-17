-- When a person became a lead: a demo form or an interested reply.
select m.person_id, f.submitted_at as lead_at, 'demo_form' as lead_source
from {{ ref('stg_ga4__form_fills') }} f
join {{ ref('int_identity__email_map') }} m using (email)
union all
select m.person_id, e.event_at, 'interested_reply'
from {{ ref('stg_smartlead__email_events') }} e
join {{ ref('int_identity__email_map') }} m using (email)
where e.event_type = 'reply' and e.reply_category = 'interested'
