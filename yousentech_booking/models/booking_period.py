from odoo import fields, models

class BookingPeriod(models.Model):
    _name = "yousentech.booking.period"
    _description = "Booking Period"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
