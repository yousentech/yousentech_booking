# Car Care Appointments — Odoo 13

Independent addon for PPF, tinting, detailing and car-care appointments. Do **not** install the repository root Odoo 17 module on Odoo 13.

## Install

Add `odoo13_addons` to Odoo 13 addons_path, update the Apps list and install `yousentech_car_appointments`. Depends on base, web and mail. Do not merge this branch into the Odoo 17 main branch.

## Screens

1. Branch configuration with One2many periods, weekday schedules, capacity, closure exceptions and provisional hold duration.
2. Responsive weekly/monthly custom calendar with Gregorian/Hijri labels, availability colors and clickable period modal.
3. Appointment form with vehicle, service, client, lifecycle and contact history.

## Capacity

Provisional/contacting bookings hold a slot until `hold_until`; confirmed/arrived bookings continue to count. Server-side advisory transaction lock serializes competing reservations. A cron expires old holds every 5 minutes.

## Verification required

This is an initial implementation committed without access to a running Odoo 13 instance. Before production use, install on an Odoo 13 test database and test module loading, view compilation, calendar asset loading, timezone/date behavior, concurrent bookings, hold expiry, record access, cancellation and contact history.
