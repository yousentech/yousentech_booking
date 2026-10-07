from odoo import fields, models

class BookingHall(models.Model):
    _name = "yousentech.booking.hall"
    _description = "Booking Hall"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    capacity = fields.Integer()
    list_price = fields.Monetary()
    currency_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)
