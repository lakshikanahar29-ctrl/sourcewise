-- Canonical person with their account. Personal contacts that never matched a work
-- contact have no account and are dropped from attribution (counted in data health).
select
    i.person_id,
    w.email                  as work_email,
    w.full_name_key,
    w.job_title,
    w.company_id,
    co.domain                as company_domain,
    w.created_at
from (select distinct person_id from {{ ref('int_identity__contacts') }}) i
join {{ ref('stg_hubspot__contacts') }} w on w.contact_id = i.person_id
left join {{ ref('stg_hubspot__companies') }} co on co.company_id = w.company_id
where w.company_id is not null
