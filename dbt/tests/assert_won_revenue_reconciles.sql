-- Credited won revenue under each model must equal won revenue in the CRM (to the cent).
with crm as (select sum(amount) as won from {{ ref('int_opportunities') }} where is_won)
select a.model, sum(a.credited_won_revenue) as credited, (select won from crm) as crm_won
from {{ ref('fct_attribution') }} a
group by a.model
having abs(sum(a.credited_won_revenue) - (select won from crm)) > 0.01
