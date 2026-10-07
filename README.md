# YousenTech Booking

Modern booking platform for **Odoo 17**.

## Direction

This repository is a clean Odoo 17 rebuild of the booking platform, keeping the proven business concepts from the previous Odoo 13 implementation while redesigning the web experience around OWL.

### Core principles

- Odoo 17 ORM, accounting, security and business rules remain the source of truth.
- Operational UI is built as a modern OWL application rather than relying on traditional Odoo forms for day-to-day reception work.
- Branch scoping remains operationally important.
- Events/halls and hotel/stay bookings remain separate domains.
- Availability, pricing, tax, accounting and lifecycle transitions are server-side business rules.
- The codebase is structured so the same backend can serve both the Odoo web client and the Flutter operations app.

## Planned domains

- Branch and security
- Customers
- Event / hall booking
- Stay / hotel booking
- Availability engines
- Services and packages
- Pricing and discounts
- Invoicing and payments
- Cancellation / reversal
- Operations dashboard
- Event planner
- Room planner
- Booking wizard
- Reports and executive dashboard
- API v2
- Migration utilities from the legacy Odoo 13 module

## Target version

Odoo 17
