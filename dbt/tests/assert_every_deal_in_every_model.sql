-- No deal may silently drop out of a model.
select o.deal_id, m.model
from {{ ref('int_opportunities') }} o
cross join (values ('first_touch'), ('last_non_direct'), ('linear'), ('w_shaped'), ('time_decay')) m(model)
where not exists (select 1 from {{ ref('fct_attribution') }} a where a.deal_id = o.deal_id and a.model = m.model)
