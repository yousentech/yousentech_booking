from odoo import fields, models, _
from odoo.exceptions import UserError

EVENT_TRANSITIONS = {
    "draft": {"hold", "confirmed", "cancelled"},
    "hold": {"confirmed", "cancelled"},
    "confirmed": {"preparing", "cancelled"},
    "preparing": {"event", "cancelled"},
    "event": {"completed"},
    "cancelled": {"draft"},
}
STAY_TRANSITIONS = {
    "draft": {"hold", "confirmed", "cancelled"},
    "hold": {"confirmed", "cancelled"},
    "confirmed": {"checked_in", "cancelled"},
    "checked_in": {"checked_out"},
    "cancelled": {"draft"},
}

class BookingLifecycleMixin(models.AbstractModel):
    _name = "yousentech.booking.lifecycle.mixin"
    _description = "Booking Lifecycle Mixin"

    cancel_reason = fields.Text(copy=False, tracking=True)
    cancelled_by_id = fields.Many2one("res.users", copy=False, readonly=True)
    cancelled_at = fields.Datetime(copy=False, readonly=True)

    def _audit(self, action, reason=None):
        for rec in self:
            self.env["yousentech.booking.audit.log"].sudo().create({
                "company_id": rec.company_id.id,
                "model_name": rec._name,
                "record_id": rec.id,
                "action": action,
                "reason": reason or False,
                "user_id": self.env.user.id,
            })

    def _transition(self, target, graph, reason=None):
        for rec in self:
            if target not in graph.get(rec.state, set()):
                raise UserError(_("This booking transition is not allowed."))
            if target == "cancelled" and not reason:
                raise UserError(_("Cancellation reason is required."))
            if target == "draft" and rec.state == "cancelled":
                rec._check_availability()
                if "invoice_ids" in rec._fields and rec.invoice_ids.filtered(lambda move: move.state == "posted"):
                    raise UserError(_("Resolve posted accounting before reopening this booking."))
            values = {"state": target}
            if target == "cancelled":
                values.update(cancel_reason=reason, cancelled_by_id=self.env.user.id, cancelled_at=fields.Datetime.now())
            elif target == "draft":
                values.update(cancel_reason=False, cancelled_by_id=False, cancelled_at=False)
            rec.with_context(booking_system_transition=True).write(values)
            rec._audit("cancel" if target == "cancelled" else ("reopen" if target == "draft" else "state"), reason or target)
        return True

class BookingEvent(models.Model):
    _inherit = ["yousentech.booking.event", "yousentech.booking.lifecycle.mixin"]
    def action_hold(self): return self._transition("hold", EVENT_TRANSITIONS)
    def action_confirm(self): return self._transition("confirmed", EVENT_TRANSITIONS)
    def action_prepare(self): return self._transition("preparing", EVENT_TRANSITIONS)
    def action_start_event(self): return self._transition("event", EVENT_TRANSITIONS)
    def action_complete(self): return self._transition("completed", EVENT_TRANSITIONS)
    def action_cancel(self, reason=None): return self._transition("cancelled", EVENT_TRANSITIONS, reason)
    def action_reopen(self): return self._transition("draft", EVENT_TRANSITIONS)

class StayBooking(models.Model):
    _inherit = ["yousentech.stay.booking", "yousentech.booking.lifecycle.mixin"]
    def action_hold(self): return self._transition("hold", STAY_TRANSITIONS)
    def action_confirm(self): return self._transition("confirmed", STAY_TRANSITIONS)
    def action_check_in(self): return self._transition("checked_in", STAY_TRANSITIONS)
    def action_check_out(self): return self._transition("checked_out", STAY_TRANSITIONS)
    def action_cancel(self, reason=None): return self._transition("cancelled", STAY_TRANSITIONS, reason)
    def action_reopen(self): return self._transition("draft", STAY_TRANSITIONS)
