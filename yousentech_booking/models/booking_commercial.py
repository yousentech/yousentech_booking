from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class BookingEventServiceLine(models.Model):
    _name = "yousentech.booking.event.service.line"
    _description = "Event Booking Service Line"

    booking_id = fields.Many2one("yousentech.booking.event", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="booking_id.company_id", store=True, index=True)
    service_id = fields.Many2one("yousentech.booking.service", required=True, domain="[('company_id','=',company_id)]")
    quantity = fields.Float(default=1.0, required=True)
    price_unit = fields.Monetary(required=True)
    subtotal = fields.Monetary(compute="_compute_subtotal", store=True)
    currency_id = fields.Many2one(related="booking_id.currency_id", store=True, readonly=True)

    @api.depends("quantity", "price_unit")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit

class BookingEvent(models.Model):
    _inherit = "yousentech.booking.event"

    package_id = fields.Many2one("yousentech.booking.package", domain="[('company_id','=',company_id)]")
    service_line_ids = fields.One2many("yousentech.booking.event.service.line", "booking_id")
    discount_type = fields.Selection([("none","No Discount"),("percent","Percentage"),("fixed","Fixed")], default="none", required=True)
    discount_value = fields.Float(default=0.0)
    amount_untaxed = fields.Monetary(compute="_compute_amounts", store=True)
    discount_amount = fields.Monetary(compute="_compute_amounts", store=True)
    amount_total = fields.Monetary(compute="_compute_amounts", store=True, tracking=True)

    @api.depends("hall_id.list_price","package_id.fixed_price","service_line_ids.subtotal","discount_type","discount_value")
    def _compute_amounts(self):
        for rec in self:
            base = (rec.hall_id.list_price or 0.0) + (rec.package_id.fixed_price or 0.0) + sum(rec.service_line_ids.mapped("subtotal"))
            discount = 0.0
            if rec.discount_type == "percent":
                discount = base * min(max(rec.discount_value, 0.0), 100.0) / 100.0
            elif rec.discount_type == "fixed":
                discount = min(max(rec.discount_value, 0.0), base)
            rec.amount_untaxed = base
            rec.discount_amount = discount
            rec.amount_total = base - discount

    @api.constrains("discount_type","discount_value")
    def _check_discount(self):
        for rec in self:
            if rec.discount_value < 0 or (rec.discount_type == "percent" and rec.discount_value > 100):
                raise ValidationError(_("Invalid discount value."))
