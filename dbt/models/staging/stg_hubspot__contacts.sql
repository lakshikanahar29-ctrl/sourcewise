select
    hs_object_id::bigint                                  as contact_id,
    lower(trim(email))                                    as email,
    split_part(lower(trim(email)), '@', 2)                as email_domain,
    split_part(lower(trim(email)), '@', 2) in ('gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com')
                                                          as is_personal_email,
    firstname                                             as first_name,
    lastname                                              as last_name,
    lower(trim(firstname || ' ' || lastname))             as full_name_key,
    jobtitle                                              as job_title,
    -- '+1 (415) 555-0134' and '4155550134' are the same phone: keep the last 10 digits
    right(regexp_replace(phone, '\D', '', 'g'), 10)       as phone_key,
    associatedcompanyid::bigint                           as company_id,
    lifecyclestage                                        as lifecycle_stage,
    createdate::timestamptz                               as created_at
from {{ source('raw', 'hubspot_contacts') }}
