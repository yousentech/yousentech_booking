from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class StayResource(models.Model):
    _name = "yousentech.stay.resource"
    _description = "Stay Resource"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", string="الشركة / الفرع", required=True, default=lambda self: self.env.company, index=True)
    resource_type = fields.Selection([("room","غرفة"),("suite","جناح"),("apartment","شقة"),("chalet","شاليه")], string="نوع المورد", default="room", required=True)
    capacity = fields.Integer(default=2)
    product_id = fields.Many2one("product.product", string="منتج الفوترة", domain="[('sale_ok','=',True)]")
    nightly_price = fields.Monetary()
    currency_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)

    @api.constrains("product_id", "company_id")
    def _check_product_company(self):
        for rec in self:
            if rec.product_id.company_id and rec.product_id.company_id != rec.company_id:
                raise ValidationError(_("منتج الفوترة يجب أن يتبع نفس شركة / فرع مورد الإقامة."))
