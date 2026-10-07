from odoo import api, fields, models

class BookingEvent(models.Model):
    _inherit = "yousentech.booking.event"
    hold_expires_at = fields.Datetime(index=True, tracking=True)

    @api.model
    def _cron_expire_holds(self):
        now = fields.Datetime.now()
        records = self.search([("state","=","hold"),("hold_expires_at","!=",False),("hold_expires_at","<=",now)])
        for rec in records:
            rec.with_context(booking_system_transition=True).write({"state":"cancelled"})
            rec._audit("cancel", "Temporary hold expired automatically.")

class StayBooking(models.Model):
    _inherit = "yousentech.stay.booking"
    hold_expires_at = fields.Datetime(index=True, tracking=True)

    @api.model
    def _cron_expire_holds(self):
        now = fields.Datetime.now()
        records = self.search([("state","=","hold"),("hold_expires_at","!=",False),("hold_expires_at","<=",now)])
        for rec in records:
            rec.with_context(booking_system_transition=True).write({"state":"cancelled"})
            rec._audit("cancel", "Temporary hold expired automatically.")
