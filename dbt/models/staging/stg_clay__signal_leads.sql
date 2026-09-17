select
    {{ dbt_utils_md5(["linkedin_post_url", "commenter_name", "company_domain", "detected_at"]) }} as signal_id,
    linkedin_post_url,
    lower(trim(commenter_name))                           as full_name_key,
    commenter_title,
    lower(trim(company_domain))                           as company_domain,
    nullif(lower(trim(work_email)), '')                   as email,
    detected_at::timestamptz                              as detected_at
from {{ source('raw', 'clay_signal_leads') }}
