from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class BookingPaymentSchedule(models.Model):
    _name="yousentech.booking.payment.schedule"
    _description="Booking Payment Schedule"
    _order="due_date, sequence, id"
    _sql_constraints=[("invoice_unique","unique(invoice_id)","An invoice can only belong to one payment schedule line.")]

    sequence=fields.Integer(default=10)
    company_id=fields.Many2one("res.company",required=True,index=True)
    event_booking_id=fields.Many2one("yousentech.booking.event",ondelete="restrict",index=True)
    stay_booking_id=fields.Many2one("yousentech.stay.booking",ondelete="restrict",index=True)
    name=fields.Char(required=True)
    due_date=fields.Date(required=True,index=True)
    amount=fields.Monetary(required=True)
    currency_id=fields.Many2one("res.currency",required=True)
    invoice_id=fields.Many2one("account.move",readonly=True,copy=False,ondelete="restrict")
    state=fields.Selection([("pending","Pending"),("invoiced","Invoiced"),("in_payment","In Payment"),("paid","Paid"),("cancelled","Cancelled")],compute="_compute_state",store=True,index=True)

    @api.depends("invoice_id.state","invoice_id.payment_state")
    def _compute_state(self):
        for rec in self:
            if not rec.invoice_id:
                rec.state="pending"
            elif rec.invoice_id.state=="cancel":
                rec.state="cancelled"
            elif rec.invoice_id.state=="posted" and rec.invoice_id.payment_state=="paid":
                rec.state="paid"
            elif rec.invoice_id.state=="posted" and rec.invoice_id.payment_state=="in_payment":
                rec.state="in_payment"
            else:
                rec.state="invoiced"

    @api.constrains("amount","event_booking_id","stay_booking_id","company_id","currency_id","invoice_id")
    def _check_values(self):
        for rec in self:
            if rec.amount<=0:
                raise ValidationError(_("Installment amount must be greater than zero."))
            if bool(rec.event_booking_id)==bool(rec.stay_booking_id):
                raise ValidationError(_("A schedule line must belong to exactly one booking."))
            booking=rec.event_booking_id or rec.stay_booking_id
            if booking and rec.company_id!=booking.company_id:
                raise ValidationError(_("Installment company must match booking company."))
            if booking and rec.currency_id!=booking.currency_id:
                raise ValidationError(_("Installment currency must match booking currency."))
            if rec.invoice_id:
                linked_booking=rec.invoice_id.yousentech_event_booking_id or rec.invoice_id.yousentech_stay_booking_id
                if linked_booking!=booking:
                    raise ValidationError(_("Installment invoice must belong to the same booking."))

    @api.model_create_multi
    def create(self,vals_list):
        for vals in vals_list:
            booking=self.env["yousentech.booking.event"].browse(vals.get("event_booking_id")) if vals.get("event_booking_id") else self.env["yousentech.stay.booking"].browse(vals.get("stay_booking_id"))
            if booking:
                vals.setdefault("company_id",booking.company_id.id)
                vals.setdefault("currency_id",booking.currency_id.id)
        return super().create(vals_list)

    def write(self,vals):
        protected={"event_booking_id","stay_booking_id","company_id","currency_id","amount","due_date"}
        if protected & set(vals) and self.filtered("invoice_id"):
            raise ValidationError(_("An invoiced installment cannot be changed."))
        if "invoice_id" in vals and not self.env.context.get("booking_schedule_system_write"):
            raise ValidationError(_("Installment invoice links are managed by the booking finance engine."))
        return super().write(vals)

    def unlink(self):
        if self.filtered("invoice_id"):
            raise ValidationError(_("An installment linked to an invoice cannot be deleted."))
        return super().unlink()
