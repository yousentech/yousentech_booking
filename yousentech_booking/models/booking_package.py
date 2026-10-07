from odoo import fields, models

class BookingPackage(models.Model):
    _name = "yousentech.booking.package"
    _description = "Booking Package"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    service_ids = fields.Many2many("yousentech.booking.service", string="Services", domain="[('company_id','=',company_id)]")
    fixed_price = fields.Monetary()
    currency_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)
