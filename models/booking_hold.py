from datetime import timedelta
from odoo import api, fields, models

DEFAULT_HOLD_MINUTES = 15
EXPIRED_REASON = "Temporary hold expired automatically."

class BookingHoldMixin(models.AbstractModel):
    _name = "yousentech.booking.hold.mixin"
    _description = "Booking Hold Mixin"

    hold_expires_at = fields.Datetime(index=True, tracking=True)

    def _set_hold_expiry(self):
        self.write({"hold_expires_at": fields.Datetime.now() + timedelta(minutes=DEFAULT_HOLD_MINUTES)})

    def _clear_hold_expiry(self):
        self.write({"hold_expires_at": False})

    def _expire_hold(self):
        for rec in self:
            if rec.state != "hold":
                continue
            rec._check_finance_before_cancel()
            now = fields.Datetime.now()
            rec.with_context(booking_system_transition=True).write({
                "state": "cancelled",
                "cancel_reason": EXPIRED_REASON,
                "cancelled_by_id": self.env.user.id,
                "cancelled_at": now,
                "hold_expires_at": False,
            })
            rec._audit("cancel", EXPIRED_REASON)

class BookingEvent(models.Model):
    _inherit = ["yousentech.booking.event", "yousentech.booking.hold.mixin"]

    def action_hold(self):
        result = super().action_hold()
        self._set_hold_expiry()
        return result

    @api.model
    def _cron_expire_holds(self):
        self.search([("state","=","hold"),("hold_expires_at","!=",False),("hold_expires_at","<=",fields.Datetime.now())])._expire_hold()

class StayBooking(models.Model):
    _inherit = ["yousentech.stay.booking", "yousentech.booking.hold.mixin"]

    def action_hold(self):
        result = super().action_hold()
        self._set_hold_expiry()
        return result

    @api.model
    def _cron_expire_holds(self):
        self.search([("state","=","hold"),("hold_expires_at","!=",False),("hold_expires_at","<=",fields.Datetime.now())])._expire_hold()
