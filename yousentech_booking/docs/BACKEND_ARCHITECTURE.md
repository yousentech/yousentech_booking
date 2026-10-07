# Backend Architecture — Odoo 17

The operational branch is standard Odoo `res.company`.

- Current branch: `env.company`
- Allowed branches: `env.companies`
- Every operational record carries `company_id`.
- Availability never crosses company boundaries.
- Accounting documents are created in the booking company.
- Event availability is Company + Hall + Date + Period(s).
- Stay availability is Company + Resource + [check-in, checkout).
- OWL is presentation only; business truth stays in Python ORM/services.

## UI boundary
Backend is intentionally prepared before expanding OWL. The next phase should design and implement each OWL screen individually.
