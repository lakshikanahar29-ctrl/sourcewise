select
    hs_object_id::bigint                                  as company_id,
    trim(name)                                            as company_name,
    lower(trim(domain))                                   as domain,
    initcap(replace(lower(industry), '_', ' '))           as industry,
    numberofemployees::int                                as employees,
    case when numberofemployees::int < 100 then 'small'
         when numberofemployees::int <= 1000 then 'mid'
         else 'large' end                                 as size_band,
    createdate::timestamptz                               as created_at
from {{ source('raw', 'hubspot_companies') }}
