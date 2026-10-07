# YousenTech Booking — Odoo 17 Roadmap

The ROADMAP is the implementation contract. Backend business truth is completed and runtime-tested before OWL screen implementation.

## Architecture decisions
- [x] Odoo 17.
- [x] Standard `res.company` is the operational branch. No custom branch model.
- [x] Event availability: Company + Hall + Date + Period(s).
- [x] Stay availability: Company + Resource + half-open interval `[check-in, checkout)`.
- [x] Odoo ORM is source of truth for availability, pricing, tax, lifecycle and finance.
- [x] OWL is presentation only.
- [x] Event and Stay are separate domains sharing customer, finance, audit and API infrastructure.

## B01 Foundation & multi-company
- [x] Module skeleton and dependencies.
- [x] Company-aware halls, periods, resources and bookings.
- [x] Allowed-company record rules for operational bookings.
- [ ] Complete company rules for every configuration/commercial/audit model.
- [ ] Cross-company integrity constraints for all relational fields.

## B02 Availability & concurrency
- [x] Event conflict validation.
- [x] Stay overlap validation with adjacent stays allowed.
- [ ] Transaction-safe locking under concurrent booking creation.
- [ ] Temporary hold expiry and scheduled release.
- [ ] Availability service test matrix.

## B03 Commercial engine
- [x] Services and packages foundation.
- [x] Discount foundation.
- [ ] Immutable commercial snapshot on confirmation.
- [ ] Taxes and fiscal-position-aware pricing.
- [ ] Package expansion rules.
- [ ] Manager-only discount authorization.
- [ ] Stay rate plans/add-ons.

## B04 Lifecycle engine
- [x] Event and stay state foundations.
- [ ] Explicit transition methods and allowed-actions service.
- [ ] Cancellation reason/actor/time.
- [ ] Safe reopen with fresh availability + finance validation.
- [ ] Event readiness/checklist.
- [ ] Check-in/check-out operational validation.

## B05 Finance
- [x] Accounting linkage foundation.
- [ ] Invoice policy: manual / full-on-confirm / deposit+final / schedule.
- [ ] Correct invoice lines, taxes and commercial snapshots.
- [ ] Payment schedule model.
- [ ] Paid/remaining/payment-state canonical computation.
- [ ] Credit note/refund-safe cancellation.
- [ ] No booking cancellation may delete posted accounting.
- [ ] Finance audit trail.

## B06 Security & audit
- [x] User/Manager groups foundation.
- [ ] Reception/Supervisor/Manager capability matrix.
- [ ] Record rules for every company-scoped model.
- [ ] Sensitive action authorization.
- [ ] Structured audit for state, cancellation, reopen, discounts and finance.

## B07 API v2
- [x] Envelope and bootstrap foundation.
- [x] Event availability foundation.
- [ ] Bearer access/refresh session model with hashed tokens and rotation.
- [ ] Event/stay CRUD and transition endpoints.
- [ ] Event board and room planner endpoints.
- [ ] Commercial quote/apply endpoints.
- [ ] Finance snapshot/schedule endpoints.
- [ ] `allowed_actions` in detail payloads.
- [ ] Stable domain error codes.
- [ ] Rate limiting / abuse controls.

## B08 Migration from legacy Odoo 13
- [ ] Mapping/run/issue models.
- [ ] Conservative event/stay migration.
- [ ] Never duplicate accounting.
- [ ] Dry-run and resumable batches.
- [ ] Migration reconciliation report.

## B09 Demo, tests & production readiness
- [ ] On-demand integrated demo builder; never auto-load demo.
- [ ] Python unit tests for availability/lifecycle/commercial/finance.
- [ ] HTTP integration tests for API.
- [ ] Multi-company isolation tests.
- [ ] Concurrency tests.
- [ ] Fresh install + upgrade tests.
- [ ] Static release gates and XML/security checks.
- [ ] Real Odoo 17 + PostgreSQL UAT.

## UI01 OWL design phase — STOP GATE
Do not implement the final OWL screens before backend B01–B09 reaches the agreed readiness gate.
Design and approve one screen at a time:
1. Operations Home
2. New Booking type selector
3. Event booking wizard
4. Event availability board
5. Event booking detail
6. Room planner
7. Stay booking wizard
8. Stay booking detail
9. Customers
10. Finance/collections
11. Mission Control/readiness
12. Executive dashboard
13. Configuration

Each screen: UX design approval first, OWL implementation second, runtime acceptance third.
