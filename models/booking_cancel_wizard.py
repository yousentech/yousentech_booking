from odoo import fields, models, _
from odoo.exceptions import UserError

class BookingCancelWizard(models.TransientModel):
    _name = "yousentech.booking.cancel.wizard"
    _description = "Booking Cancellation"

    reason = fields.Text(string="سبب الإلغاء", required=True)

    def action_confirm_cancel(self):
        self.ensure_one()
        active_model = self.env.context.get("active_model")
        active_id = self.env.context.get("active_id")
        if active_model not in ("yousentech.booking.event", "yousentech.stay.booking") or not active_id:
            raise UserError(_("Invalid booking cancellation context."))
        booking = self.env[active_model].browse(active_id).exists()
        if not booking:
            raise UserError(_("Booking not found."))
        booking.action_cancel(reason=self.reason)
        return {"type": "ir.actions.act_window_close"}
