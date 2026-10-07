from odoo import fields, models

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
