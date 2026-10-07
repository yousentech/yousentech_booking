from datetime import timedelta
from odoo import api, fields, models

DEFAULT_HOLD_MINUTES = 15

class BookingEvent(models.Model):
    _inherit = "yousentech.booking.event"
    hold_expires_at = fields.Datetime(index=True, tracking=True)

    def action_hold(self):
        for rec in self:
            if not rec.hold_expires_at:
                rec.hold_expires_at = fields.Datetime.now() + timedelta(minutes=DEFAULT_HOLD_MINUTES)
        return super().action_hold()

    @api.model
    def _cron_expire_holds(self):
        now = fields.Datetime.now()
        records = self.search([("state","=","hold"),("hold_expires_at","!=",False),("hold_expires_at","<=",now)])
        for rec in records:
            rec.with_context(booking_system_transition=True).write({"state":"cancelled","cancel_reason":"Temporary hold expired automatically.","cancelled_at":now})
            rec._audit("cancel", "Temporary hold expired automatically.")

class StayBooking(models.Model):
    _inherit = "yousentech.stay.booking"
    hold_expires_at = fields.Datetime(index=True, tracking=True)

    def action_hold(self):
        for rec in self:
            if not rec.hold_expires_at:
                rec.hold_expires_at = fields.Datetime.now() + timedelta(minutes=DEFAULT_HOLD_MINUTES)
        return super().action_hold()

    @api.model
    def _cron_expire_holds(self):
        now = fields.Datetime.now()
        records = self.search([("state","=","hold"),("hold_expires_at","!=",False),("hold_expires_at","<=",now)])
        for rec in records:
            rec.with_context(booking_system_transition=True).write({"state":"cancelled","cancel_reason":"Temporary hold expired automatically.","cancelled_at":now})
            rec._audit("cancel", "Temporary hold expired automatically.")
