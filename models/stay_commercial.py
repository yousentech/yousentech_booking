from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

LOCKED_STATES=("confirmed","checked_in","checked_out")

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
            booking=self.env["yousentech.stay.booking"].browse(vals.get("booking_id")) if vals.get("booking_id") else False
            if booking and booking.state in LOCKED_STATES: raise ValidationError(_("Confirmed booking add-ons cannot be changed."))
            addon=self.env["yousentech.stay.addon"].browse(vals.get("addon_id")) if vals.get("addon_id") else False
            if addon and "price_unit" not in vals: vals["price_unit"]=addon.price
        return super().create(vals_list)

    def write(self,vals):
        if self.filtered(lambda l:l.booking_id.state in LOCKED_STATES): raise ValidationError(_("Confirmed booking add-ons cannot be changed."))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda l:l.booking_id.state in LOCKED_STATES): raise ValidationError(_("Confirmed booking add-ons cannot be deleted."))
        return super().unlink()

class StayBooking(models.Model):
    _inherit = "yousentech.stay.booking"
    rate_plan_id = fields.Many2one("yousentech.stay.rate.plan", domain="[('company_id','=',company_id)]")
    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        company_id = vals.get("company_id") or self.env.context.get("default_company_id") or self.env.company.id
        settings = self.env["yousentech.booking.settings"].search([("company_id", "=", company_id)], limit=1)
        if settings:
            if "rate_plan_id" in fields_list and not vals.get("rate_plan_id") and not self.env.context.get("default_rate_plan_id") and settings.stay_default_rate_plan_id:
                vals["rate_plan_id"] = settings.stay_default_rate_plan_id.id
            if "invoice_policy" in fields_list and not self.env.context.get("default_invoice_policy"):
                vals["invoice_policy"] = settings.stay_invoice_policy
            if "deposit_percent" in fields_list and not self.env.context.get("default_deposit_percent"):
                vals["deposit_percent"] = settings.stay_deposit_percent
        return vals

    addon_line_ids = fields.One2many("yousentech.stay.booking.addon.line","booking_id")
    discount_type=fields.Selection([("none","بدون خصم"),("percent","نسبة"),("fixed","مبلغ ثابت")],default="none",required=True)
    discount_value=fields.Float(default=0.0)
    discount_amount=fields.Monetary(compute="_compute_commercial",store=True)
    nights = fields.Integer(compute="_compute_commercial", store=True)
    nightly_price = fields.Monetary(compute="_compute_commercial", store=True)
    amount_untaxed = fields.Monetary(compute="_compute_commercial", store=True)
    tax_amount = fields.Monetary(compute="_compute_commercial", store=True)
    amount_total = fields.Monetary(compute="_compute_commercial", store=True, tracking=True)

    @api.depends("checkin_date","checkout_date","resource_id.nightly_price","rate_plan_id.pricing_type","rate_plan_id.fixed_price","rate_plan_id.percent_adjustment","rate_plan_id.tax_id","addon_line_ids.subtotal","discount_type","discount_value","partner_id")
    def _compute_commercial(self):
        for rec in self:
            nights = (rec.checkout_date-rec.checkin_date).days if rec.checkin_date and rec.checkout_date and rec.checkout_date > rec.checkin_date else 0
            price = rec.resource_id.nightly_price or 0.0
            if rec.rate_plan_id.pricing_type == "fixed":
                price = rec.rate_plan_id.fixed_price or 0.0
            elif rec.rate_plan_id.pricing_type == "percent":
                price *= 1 + (rec.rate_plan_id.percent_adjustment or 0.0) / 100.0
            rec.nights, rec.nightly_price = nights, price
            tax = rec.rate_plan_id.tax_id
            def split(unit, qty, product=False):
                if not tax:
                    return unit * qty
                return tax.compute_all(unit, currency=rec.currency_id, quantity=qty, product=product, partner=rec.partner_id)["total_excluded"]
            gross = split(price, nights, rec.resource_id.product_id)
            for line in rec.addon_line_ids:
                qty = line.quantity * (nights if line.addon_id.charge_type == "night" else 1)
                gross += split(line.price_unit, qty, line.addon_id.product_id)
            discount = gross * rec.discount_value / 100 if rec.discount_type == "percent" else min(rec.discount_value, gross) if rec.discount_type == "fixed" else 0.0
            discount = max(discount, 0.0)
            factor = (gross-discount)/gross if gross else 1.0
            def tax_part(unit, qty, product=False):
                if not tax:
                    return 0.0
                result = tax.compute_all(unit*factor, currency=rec.currency_id, quantity=qty, product=product, partner=rec.partner_id)
                return result["total_included"]-result["total_excluded"]
            taxes = tax_part(price, nights, rec.resource_id.product_id)
            for line in rec.addon_line_ids:
                qty = line.quantity * (nights if line.addon_id.charge_type == "night" else 1)
                taxes += tax_part(line.price_unit, qty, line.addon_id.product_id)
            rec.discount_amount = discount
            rec.amount_untaxed = gross-discount
            rec.tax_amount = taxes
            rec.amount_total = rec.amount_untaxed+taxes

    @api.constrains("discount_type","discount_value")
    def _check_discount(self):
        for rec in self:
            if rec.discount_value < 0 or (rec.discount_type == "percent" and rec.discount_value > 100):
                raise ValidationError(_("Invalid booking discount."))

    @api.constrains("rate_plan_id","addon_line_ids")
    def _check_commercial_company(self):
        for rec in self:
            if rec.rate_plan_id and rec.rate_plan_id.company_id!=rec.company_id: raise ValidationError(_("Rate plan must belong to the booking branch/company."))
            if rec.addon_line_ids.filtered(lambda l:l.company_id!=rec.company_id or l.addon_id.company_id!=rec.company_id): raise ValidationError(_("All add-ons must belong to the booking branch/company."))

    def write(self,vals):
        if {"rate_plan_id","addon_line_ids","discount_type","discount_value","resource_id","checkin_date","checkout_date"} & set(vals) and self.filtered(lambda r:r.state in LOCKED_STATES): raise ValidationError(_("Confirmed commercial terms are locked. Cancel and reopen the booking before changing them."))
        return super().write(vals)
