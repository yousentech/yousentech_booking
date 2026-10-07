{
    "name": "YousenTech Booking",
    "version": "17.0.3.0.0",
    "summary": "Modern event and stay booking operations",
    "category": "Services/Booking",
    "author": "YousenTech",
    "license": "LGPL-3",
    "depends": ["base", "web", "mail", "account", "product"],
    "data": [
        "security/booking_security.xml",
        "security/ir.model.access.csv",
        "data/booking_sequence.xml",
        "data/booking_cron.xml",
        "views/booking_views.xml",
        "views/booking_menu.xml"
    ],
    "assets": {"web.assets_backend": ["yousentech_booking/static/src/booking_os/**/*"]},
    "application": true,
    "installable": true
}
