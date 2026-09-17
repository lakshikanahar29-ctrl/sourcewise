-- GA4 cookie -> person, learned from demo form fills. A cookie that never filled a form stays anonymous.
select client_id, min(person_id) as person_id, min(submitted_at) as first_identified_at
from {{ ref('stg_ga4__form_fills') }} f
join {{ ref('int_identity__email_map') }} m using (email)
group by client_id
