-- One person per human. HubSpot holds some people twice: a work contact and a personal
-- gmail contact created by a demo form. They share a phone number, so merge on it.
with contacts as (
    select * from {{ ref('stg_hubspot__contacts') }}
),
work as (
    select * from contacts where not is_personal_email
),
personal_matched as (
    select p.contact_id, w.contact_id as person_id, 'phone_match' as match_rule
    from contacts p
    join work w on w.phone_key = p.phone_key
    where p.is_personal_email
)
select c.contact_id,
       c.email,
       coalesce(pm.person_id, c.contact_id)                         as person_id,
       coalesce(pm.match_rule, case when c.is_personal_email then 'unmatched_personal' else 'self' end) as match_rule
from contacts c
left join personal_matched pm on pm.contact_id = c.contact_id
