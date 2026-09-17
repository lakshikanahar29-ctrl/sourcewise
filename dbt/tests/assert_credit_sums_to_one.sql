-- Every deal must hand out exactly 1.0 credit under every model.
select deal_id, model, sum(credit) as total_credit
from {{ ref('fct_attribution') }}
group by 1, 2
having abs(sum(credit) - 1) > 0.00001
