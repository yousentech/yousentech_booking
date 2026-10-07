from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class StayBookingAddonLine(models.Model):
    _name = "yousentech.stay.booking.addon.line"
    _description = "Stay Booking Add-on Line"

    booking_id = fields.Many2one("yousentech.stay.booking", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="booking_id.company_id", store=True, index=True)
    addon_id = fields.Many2one("yousentech.stay.addon", required=True, domain="[('company_id','=',company_id)]")
    quantity = fields.Float(default=1.0, required=True)
    price_unit = fields.Monetary(required=True)
    subtotal = fields.Monetary(compute="_compute_subtotal", store=True)
    currency_id = fields.Many2one(related="booking_id.currency_id", store=True, readonly=True)

    @api.depends("quantity","price_unit")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit

class StayBooking(models.Model):
    _inherit = "yousentech.stay.booking"

    rate_plan_id = fields.Many2one("yousentech.stay.rate.plan", domain="[('company_id','=',company_id)]")
    addon_line_ids = fields.One2many("yousentech.stay.booking.addon.line","booking_id")
    nights = fields.Integer(compute="_compute_commercial", store=True)
    nightly_price = fields.Monetary(compute="_compute_commercial", store=True)
    amount_untaxed = fields.Monetary(compute="_compute_commercial", store=True)
    amount_total = fields.Monetary(compute="_compute_commercial", store=True, tracking=True)

    @api.depends("checkin_date","checkout_date","resource_id.nightly_price","rate_plan_id.pricing_type","rate_plan_id.fixed_price","rate_plan_id.percent_adjustment","addon_line_ids.subtotal")
    def _compute_commercial(self):
        for rec in self:
            nights = (rec.checkout_date - rec.checkin_date).days if rec.checkin_date and rec.checkout_date and rec.checkout_date > rec.checkin_date else 0
            base_price = rec.resource_id.nightly_price or 0.0
            if rec.rate_plan_id.pricing_type == "fixed":
                base_price = rec.rate_plan_id.fixed_price or 0.0
            elif rec.rate_plan_id.pricing_type == "percent":
                base_price *= 1.0 + (rec.rate_plan_id.percent_adjustment or 0.0) / 100.0
            rec.nights = nights
            rec.nightly_price = base_price
            rec.amount_untaxed = nights * base_price + sum(rec.addon_line_ids.mapped("subtotal"))
            rec.amount_total = rec.amount_untaxed

    @api.constrains("rate_plan_id","addon_line_ids")
    def _check_commercial_company(self):
        for rec in self:
            if rec.rate_plan_id and rec.rate_plan_id.company_id != rec.company_id:
                raise ValidationError(_("Rate plan must belong to the booking branch/company."))
            if rec.addon_line_ids.filtered(lambda l: l.company_id != rec.company_id or l.addon_id.company_id != rec.company_id):
                raise ValidationError(_("All add-ons must belong to the booking branch/company."))
