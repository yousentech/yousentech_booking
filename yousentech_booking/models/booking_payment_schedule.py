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
    state=fields.Selection([("pending","Pending"),("invoiced","Invoiced"),("paid","Paid"),("cancelled","Cancelled")],default="pending",required=True,index=True)

    @api.constrains("amount","event_booking_id","stay_booking_id")
    def _check_values(self):
        for rec in self:
            if rec.amount<=0: raise ValidationError(_("Installment amount must be greater than zero."))
            if bool(rec.event_booking_id)==bool(rec.stay_booking_id): raise ValidationError(_("A schedule line must belong to exactly one booking."))
