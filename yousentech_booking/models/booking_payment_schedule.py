from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class BookingPaymentSchedule(models.Model):
    _name="yousentech.booking.payment.schedule"
    _description="Booking Payment Schedule"
    _order="due_date, sequence, id"

    sequence=fields.Integer(default=10)
    company_id=fields.Many2one("res.company",required=True,index=True)
    event_booking_id=fields.Many2one("yousentech.booking.event",ondelete="cascade",index=True)
    stay_booking_id=fields.Many2one("yousentech.stay.booking",ondelete="cascade",index=True)
    name=fields.Char(required=True)
    due_date=fields.Date(required=True,index=True)
    amount=fields.Monetary(required=True)
    currency_id=fields.Many2one("res.currency",required=True)
    invoice_id=fields.Many2one("account.move",readonly=True,copy=False)
    state=fields.Selection([("pending","Pending"),("invoiced","Invoiced"),("paid","Paid"),("cancelled","Cancelled")],compute="_compute_state",store=True,index=True)

    @api.depends("invoice_id.state","invoice_id.payment_state")
    def _compute_state(self):
        for rec in self:
            if not rec.invoice_id: rec.state="pending"
            elif rec.invoice_id.state=="cancel": rec.state="cancelled"
            elif rec.invoice_id.state=="posted" and rec.invoice_id.payment_state in ("paid","in_payment"): rec.state="paid"
            else: rec.state="invoiced"

    @api.constrains("amount","event_booking_id","stay_booking_id","company_id","currency_id")
    def _check_values(self):
        for rec in self:
            if rec.amount<=0: raise ValidationError(_("Installment amount must be greater than zero."))
            if bool(rec.event_booking_id)==bool(rec.stay_booking_id): raise ValidationError(_("A schedule line must belong to exactly one booking."))
            booking=rec.event_booking_id or rec.stay_booking_id
            if booking and rec.company_id!=booking.company_id: raise ValidationError(_("Installment company must match booking company."))
            if booking and rec.currency_id!=booking.currency_id: raise ValidationError(_("Installment currency must match booking currency."))

    @api.model_create_multi
    def create(self,vals_list):
        for vals in vals_list:
            booking=self.env["yousentech.booking.event"].browse(vals.get("event_booking_id")) if vals.get("event_booking_id") else self.env["yousentech.stay.booking"].browse(vals.get("stay_booking_id"))
            if booking:
                vals.setdefault("company_id",booking.company_id.id); vals.setdefault("currency_id",booking.currency_id.id)
        return super().create(vals_list)
