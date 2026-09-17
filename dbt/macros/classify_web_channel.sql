{#
  Web session -> channel. Rules are ordered; first match wins.
  Known limitation (on purpose): paid clicks that lost their UTMs cannot be told apart
  from organic traffic, so they land in organic_social / organic_search / direct.
#}
{% macro classify_web_channel(utm_source, utm_medium, referrer) -%}
case
    when {{ utm_source }} in ('linkedin', 'linkedin_ads')                 then 'linkedin_ads'
    when {{ utm_source }} = 'google' and {{ utm_medium }} = 'cpc'         then 'google_ads'
    when {{ utm_source }} = 'adroll'                                      then 'retargeting_ads'
    when {{ referrer }} = 'linkedin.com'                                  then 'organic_social'
    when {{ referrer }} in ('google.com', 'bing.com')                     then 'organic_search'
    when {{ referrer }} in ('g2.com', 'capterra.com', 'legaltechpartners.io') then 'referral'
    when {{ utm_source }} is null and {{ referrer }} is null              then 'direct'
    else 'other'
end
{%- endmacro %}
