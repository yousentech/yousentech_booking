from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class BookingService(models.Model):
    _name="yousentech.booking.service"
    _description="Booking Service"
    _order="sequence, name"

    name=fields.Char(required=True,translate=True)
    sequence=fields.Integer(default=10)
    active=fields.Boolean(default=True)
    company_id=fields.Many2one("res.company",required=True,default=lambda self:self.env.company,index=True)
    product_id=fields.Many2one("product.product",required=True,domain="[('sale_ok','=',True)]")
    price=fields.Monetary(required=True)
    tax_ids=fields.Many2many("account.tax",string="Taxes",domain="[('company_id','=',company_id),('type_tax_use','in',('sale','none'))]")
    currency_id=fields.Many2one(related="company_id.currency_id",store=True,readonly=True)

    @api.constrains("company_id","product_id","tax_ids","price")
    def _check_configuration(self):
        for rec in self:
            if rec.price<0:
                raise ValidationError(_("Service price cannot be negative."))
            if rec.product_id.company_id and rec.product_id.company_id!=rec.company_id:
                raise ValidationError(_("Service product must be global or belong to the same branch/company."))
            if rec.tax_ids.filtered(lambda tax:tax.company_id!=rec.company_id):
                raise ValidationError(_("Service taxes must belong to the same branch/company."))
