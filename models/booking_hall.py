from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class BookingHall(models.Model):
    _name = "yousentech.booking.hall"
    _description = "Booking Hall"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    capacity = fields.Integer()
    product_id = fields.Many2one("product.product", string="منتج الفوترة", domain="[('sale_ok','=',True)]")
    list_price = fields.Monetary()
    currency_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)

    @api.constrains("product_id", "company_id")
    def _check_product_company(self):
        for rec in self:
            if rec.product_id.company_id and rec.product_id.company_id != rec.company_id:
                raise ValidationError(_("منتج الفوترة يجب أن يتبع نفس شركة / فرع القاعة."))
