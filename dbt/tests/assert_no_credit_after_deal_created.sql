-- A touch after the deal was created cannot have caused it.
select * from {{ ref('fct_attribution') }}
where touched_at > deal_created_at
