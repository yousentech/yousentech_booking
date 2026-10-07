from odoo import api, fields, models, _
from odoo.exceptions import ValidationError\n\nLOCKED_STATES=("confirmed","checked_in","checked_out")

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

    @api.depends("quantity","price_unit","addon_id.charge_type","booking_id.checkin_date","booking_id.checkout_date")
    def _compute_subtotal(self):
        for line in self:
            nights=(line.booking_id.checkout_date-line.booking_id.checkin_date).days if line.booking_id.checkin_date and line.booking_id.checkout_date and line.booking_id.checkout_date>line.booking_id.checkin_date else 0
            multiplier=nights if line.addon_id.charge_type=="night" else 1
            line.subtotal=line.quantity*line.price_unit*multiplier

    @api.constrains("addon_id","quantity")
    def _check_line_values(self):
        for line in self:
            if line.quantity<=0: raise ValidationError(_("Add-on quantity must be greater than zero."))
            if line.addon_id and line.booking_id and line.addon_id.company_id!=line.booking_id.company_id: raise ValidationError(_("Add-on must belong to the booking branch/company."))

    @api.onchange("addon_id")
    def _onchange_addon_id(self):
        if self.addon_id: self.price_unit=self.addon_id.price

    @api.model_create_multi
    def create(self,vals_list):
        for vals in vals_list:
            addon=self.env["yousentech.stay.addon"].browse(vals.get("addon_id")) if vals.get("addon_id") else False
            if addon and "price_unit" not in vals: vals["price_unit"]=addon.price
        return super().create(vals_list)

class StayBooking(models.Model):
    _inherit = "yousentech.stay.booking"
    rate_plan_id = fields.Many2one("yousentech.stay.rate.plan", domain="[('company_id','=',company_id)]")
    addon_line_ids = fields.One2many("yousentech.stay.booking.addon.line","booking_id")
    nights = fields.Integer(compute="_compute_commercial", store=True)
    nightly_price = fields.Monetary(compute="_compute_commercial", store=True)
    amount_untaxed = fields.Monetary(compute="_compute_commercial", store=True)
    tax_amount = fields.Monetary(compute="_compute_commercial", store=True)
    amount_total = fields.Monetary(compute="_compute_commercial", store=True, tracking=True)

    @api.depends("checkin_date","checkout_date","resource_id.nightly_price","rate_plan_id.pricing_type","rate_plan_id.fixed_price","rate_plan_id.percent_adjustment","addon_line_ids.subtotal","addon_line_ids.addon_id.tax_ids","partner_id")
    def _compute_commercial(self):
        for rec in self:
            nights=(rec.checkout_date-rec.checkin_date).days if rec.checkin_date and rec.checkout_date and rec.checkout_date>rec.checkin_date else 0
            base_price=rec.resource_id.nightly_price or 0.0
            if rec.rate_plan_id.pricing_type=="fixed": base_price=rec.rate_plan_id.fixed_price or 0.0
            elif rec.rate_plan_id.pricing_type=="percent": base_price*=1.0+(rec.rate_plan_id.percent_adjustment or 0.0)/100.0
            rec.nights=nights; rec.nightly_price=base_price
            rec.amount_untaxed=nights*base_price+sum(rec.addon_line_ids.mapped("subtotal"))
            tax_amount=0.0
            for line in rec.addon_line_ids:
                quantity=line.quantity*(nights if line.addon_id.charge_type=="night" else 1)
                taxes=line.addon_id.tax_ids.compute_all(line.price_unit,currency=rec.currency_id,quantity=quantity,product=line.addon_id.product_id,partner=rec.partner_id)
                tax_amount+=taxes["total_included"]-taxes["total_excluded"]
            rec.tax_amount=tax_amount
            rec.amount_total=rec.amount_untaxed+tax_amount

    @api.constrains("rate_plan_id","addon_line_ids")
    def _check_commercial_company(self):
        for rec in self:
            if rec.rate_plan_id and rec.rate_plan_id.company_id!=rec.company_id: raise ValidationError(_("Rate plan must belong to the booking branch/company."))
            if rec.addon_line_ids.filtered(lambda l:l.company_id!=rec.company_id or l.addon_id.company_id!=rec.company_id): raise ValidationError(_("All add-ons must belong to the booking branch/company."))
\n    def write(self,vals):\n        if {"rate_plan_id","addon_line_ids","resource_id","checkin_date","checkout_date"} & set(vals) and self.filtered(lambda r:r.state in LOCKED_STATES): raise ValidationError(_("Confirmed commercial terms are locked. Cancel and reopen the booking before changing them."))\n        return super().write(vals)\n