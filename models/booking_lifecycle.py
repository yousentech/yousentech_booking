from odoo import fields, models, _
from odoo.exceptions import AccessError, UserError

EVENT_TRANSITIONS={"draft":{"hold","confirmed","cancelled"},"hold":{"confirmed","cancelled"},"confirmed":{"preparing","cancelled"},"preparing":{"event","cancelled"},"event":{"completed","cancelled"},"completed":{"cancelled"},"cancelled":{"draft"}}
STAY_TRANSITIONS={"draft":{"hold","confirmed","cancelled"},"hold":{"confirmed","cancelled"},"confirmed":{"checked_in","cancelled"},"checked_in":{"checked_out"},"cancelled":{"draft"}}

class BookingLifecycleMixin(models.AbstractModel):
    _name="yousentech.booking.lifecycle.mixin"
    _description="Booking Lifecycle Mixin"
    cancel_reason=fields.Text(copy=False,tracking=True)
    cancelled_by_id=fields.Many2one("res.users",copy=False,readonly=True)
    cancelled_at=fields.Datetime(copy=False,readonly=True)

    def _audit(self,action,reason=None):
        for rec in self:
            self.env["yousentech.booking.audit.log"].sudo().create({"company_id":rec.company_id.id,"model_name":rec._name,"record_id":rec.id,"action":action,"reason":reason or False,"user_id":self.env.user.id})

    def _require_group(self,xmlid,message):
        if not self.env.user.has_group(xmlid):
            raise AccessError(message)

    def _readiness_errors(self,target):
        self.ensure_one()
        errors=[]
        if not self.partner_id:
            errors.append(_("Customer is required."))
        if self._name=="yousentech.booking.event":
            if not self.hall_id: errors.append(_("Hall is required."))
            if not self.booking_date: errors.append(_("Booking date is required."))
            if not self.period_ids: errors.append(_("At least one period is required."))
        else:
            if not self.resource_id: errors.append(_("Stay resource is required."))
            if not self.checkin_date: errors.append(_("تاريخ الدخول إجباري."))
            if not self.checkout_date and not self.company_id.booking_allow_open_stay: errors.append(_("تاريخ الخروج إجباري حسب إعدادات الشركة / الفرع."))
            if target in ("confirmed","checked_in","checked_out") and not self.checkout_date: errors.append(_("يجب تحديد تاريخ الخروج قبل تأكيد الحجز أو تسجيل الدخول حتى يمكن تثبيت المدة والتسعير."))
        if target=="confirmed" and self.amount_total<=0:
            errors.append(_("Booking total must be greater than zero before confirmation."))
        if target in ("preparing","event","checked_in") and self.finance_state=="not_invoiced" and self.invoice_policy!="manual":
            errors.append(_("Required booking invoice has not been created."))
        return errors

    def _check_readiness(self,target):
        errors=self._readiness_errors(target)
        if errors:
            raise UserError("\n".join(errors))

    def _allowed_actions(self):
        self.ensure_one()
        actions=sorted(EVENT_TRANSITIONS.get(self.state,set()) if self._name=="yousentech.booking.event" else STAY_TRANSITIONS.get(self.state,set()))
        if not self.env.user.has_group("yousentech_booking.group_booking_supervisor"):
            actions=[a for a in actions if a not in ("cancelled","draft")]
        return actions

    def _transition(self,target,graph,reason=None):
        for rec in self:
            rec.flush_recordset(["state"])
            rec.env.cr.execute("SELECT id FROM %s WHERE id = %%s FOR UPDATE" % rec._table,[rec.id])
            rec.invalidate_recordset(["state"],flush=False)
            if target not in graph.get(rec.state,set()):
                raise UserError(_("This booking transition is not allowed."))
            if target in ("cancelled","draft"):
                rec._require_group("yousentech_booking.group_booking_supervisor",_("Only a booking supervisor can cancel or reopen bookings."))
            if target=="cancelled" and not reason:
                raise UserError(_("Cancellation reason is required."))
            rec._check_readiness(target)
            if target=="cancelled":
                rec._check_finance_before_cancel()
            if target=="draft" and rec.state=="cancelled":
                rec._check_availability(lock=True)
                rec._check_finance_before_cancel()

            apply_confirmation_policy=target=="confirmed"
            if apply_confirmation_policy:
                rec._check_availability(lock=True)
                rec._create_commercial_snapshot()

            vals={"state":target}
            if target=="cancelled":
                vals.update(cancel_reason=reason,cancelled_by_id=self.env.user.id,cancelled_at=fields.Datetime.now())
            elif target=="draft":
                vals.update(cancel_reason=False,cancelled_by_id=False,cancelled_at=False)
            if target!="hold" and "hold_expires_at" in rec._fields:
                vals["hold_expires_at"]=False

            rec.with_context(booking_system_transition=True).write(vals)
            if apply_confirmation_policy:
                rec._apply_confirmation_invoice_policy()
            rec._audit("cancel" if target=="cancelled" else ("reopen" if target=="draft" else "state"),reason or target)
        return True

class BookingEvent(models.Model):
    _name="yousentech.booking.event"
    _inherit=["yousentech.booking.event","yousentech.booking.lifecycle.mixin"]
    def action_hold(self): return self._transition("hold",EVENT_TRANSITIONS)
    def action_confirm(self): return self._transition("confirmed",EVENT_TRANSITIONS)
    def action_prepare(self): return self._transition("preparing",EVENT_TRANSITIONS)
    def action_start_event(self): return self._transition("event",EVENT_TRANSITIONS)
    def action_complete(self): return self._transition("completed",EVENT_TRANSITIONS)
    def action_cancel(self,reason=None): return self._transition("cancelled",EVENT_TRANSITIONS,reason)
    def action_reopen(self): return self._transition("draft",EVENT_TRANSITIONS)

class StayBooking(models.Model):
    _name="yousentech.stay.booking"
    _inherit=["yousentech.stay.booking","yousentech.booking.lifecycle.mixin"]
    def action_hold(self): return self._transition("hold",STAY_TRANSITIONS)
    def action_confirm(self): return self._transition("confirmed",STAY_TRANSITIONS)
    def action_check_in(self): return self._transition("checked_in",STAY_TRANSITIONS)
    def action_check_out(self): return self._transition("checked_out",STAY_TRANSITIONS)
    def action_cancel(self,reason=None): return self._transition("cancelled",STAY_TRANSITIONS,reason)
    def action_reopen(self): return self._transition("draft",STAY_TRANSITIONS)
