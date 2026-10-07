from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class StayRatePlan(models.Model):
    _name="yousentech.stay.rate.plan"
    _description="Stay Rate Plan"
    _order="sequence, name"
    name=fields.Char(required=True,translate=True)
    sequence=fields.Integer(default=10)
    active=fields.Boolean(default=True)
    company_id=fields.Many2one("res.company",required=True,default=lambda self:self.env.company,index=True)
    pricing_type=fields.Selection([("fixed","Fixed Nightly Price"),("resource","Resource Price"),("percent","Resource Price Adjustment")],default="resource",required=True)
    fixed_price=fields.Monetary()
    percent_adjustment=fields.Float()
    currency_id=fields.Many2one(related="company_id.currency_id",store=True,readonly=True)

    @api.constrains("pricing_type","fixed_price","percent_adjustment")
    def _check_pricing(self):
        for rec in self:
            if rec.pricing_type=="fixed" and rec.fixed_price<0:
                raise ValidationError(_("Fixed nightly price cannot be negative."))
            if rec.pricing_type=="percent" and rec.percent_adjustment<=-100:
                raise ValidationError(_("Rate adjustment must be greater than -100%."))

class StayAddon(models.Model):
    _name="yousentech.stay.addon"
    _description="Stay Add-on"
    _order="sequence, name"
    name=fields.Char(required=True,translate=True)
    sequence=fields.Integer(default=10)
    active=fields.Boolean(default=True)
    company_id=fields.Many2one("res.company",required=True,default=lambda self:self.env.company,index=True)
    product_id=fields.Many2one("product.product",required=True)
    price=fields.Monetary(required=True)
    charge_type=fields.Selection([("once","Once"),("night","Per Night")],default="once",required=True)
    tax_ids=fields.Many2many("account.tax",string="Taxes",domain="[('company_id','=',company_id),('type_tax_use','in',('sale','none'))]")
    currency_id=fields.Many2one(related="company_id.currency_id",store=True,readonly=True)

    @api.constrains("company_id","product_id","tax_ids","price")
    def _check_configuration(self):
        for rec in self:
            if rec.price<0:
                raise ValidationError(_("Add-on price cannot be negative."))
            if rec.product_id.company_id and rec.product_id.company_id!=rec.company_id:
                raise ValidationError(_("Add-on product must be global or belong to the same branch/company."))
            if rec.tax_ids.filtered(lambda tax:tax.company_id!=rec.company_id):
                raise ValidationError(_("Add-on taxes must belong to the same branch/company."))
