-- Every known email address -> person.
select distinct i.email, i.person_id
from {{ ref('int_identity__contacts') }} i
join {{ ref('int_identity__people') }} p using (person_id)
