from odoo import fields, models

class BookingService(models.Model):
    _name = "yousentech.booking.service"
    _description = "Booking Service"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    product_id = fields.Many2one("product.product", required=True, domain="[('sale_ok','=',True)]")
    price = fields.Monetary(required=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)
