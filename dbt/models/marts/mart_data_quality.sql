-- One row per check, so the dashboard can show a health table and the pipeline can alert on thresholds.
with paid_sessions as (
    select count(*) filter (where channel in ('linkedin_ads', 'google_ads', 'retargeting_ads')) as tagged_paid_sessions
    from {{ ref('stg_ga4__sessions') }}
),
paid_clicks as (select sum(clicks) as clicks from {{ ref('stg_ads__spend_daily') }}),
won as (select sum(amount) as won from {{ ref('int_opportunities') }} where is_won),
unattr as (select coalesce(sum(credited_won_revenue), 0) as rev from {{ ref('fct_attribution') }} where model = 'linear' and channel = 'unattributed'),
checks as (
    select 'utm_coverage_paid_clicks' as check_name,
           'Share of ad-platform clicks that arrived on the site with UTMs' as description,
           round((select tagged_paid_sessions from paid_sessions)::numeric / (select clicks from paid_clicks), 3) as value,
           0.80 as threshold, 'min' as direction
    union all
    select 'identified_session_share', 'Share of web sessions stitched to a known person',
           round(avg((c.client_id is not null)::int), 3), 0.10, 'min'
    from {{ ref('stg_ga4__sessions') }} s left join {{ ref('int_identity__client_map') }} c using (client_id)
    union all
    select 'unattributed_won_revenue_share', 'Share of won revenue with no touch in the lookback window',
           round((select rev from unattr) / nullif((select won from won), 0), 3), 0.20, 'max'
    union all
    select 'deals_missing_contact_share', 'Share of deals with no associated contact in HubSpot',
           round(avg(is_missing_contact::int), 3), 0.10, 'max' from {{ ref('int_opportunities') }}
    union all
    select 'personal_email_contacts_merged', 'Duplicate gmail contacts merged into a work contact by phone',
           count(*) filter (where match_rule = 'phone_match'), null, 'info' from {{ ref('int_identity__contacts') }}
    union all
    select 'personal_email_contacts_unmatched', 'Gmail contacts that could not be merged',
           count(*) filter (where match_rule = 'unmatched_personal'), 5, 'max' from {{ ref('int_identity__contacts') }}
    union all
    select 'clay_signals_matched_share', 'Clay signal rows matched to a CRM person (incl. no-email rows matched on name + domain)',
           round((select count(distinct source_record_id) from {{ ref('int_touchpoints') }} where source_system = 'clay')::numeric
                 / nullif((select count(*) from {{ ref('stg_clay__signal_leads') }}), 0), 3), 0.90, 'min'
    union all
    select 'reopened_won_deals', 'Won deals that were marked closed-lost first (would be double counted by a history-based metric)',
           count(*) filter (where was_reopened), null, 'info' from {{ ref('int_opportunities') }}
)
select *,
       case when direction = 'min' and value < threshold then 'warn'
            when direction = 'max' and value > threshold then 'warn'
            else 'ok' end as status,
       now() as checked_at
from checks
