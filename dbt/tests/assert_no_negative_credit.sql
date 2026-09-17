select * from {{ ref('fct_attribution') }} where credit < 0 or credit > 1
