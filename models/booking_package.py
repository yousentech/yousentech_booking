from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class BookingPackageLine(models.Model):
    _name = "yousentech.booking.package.line"
    _description = "Booking Package Line"
    _order = "sequence, id"

    package_id = fields.Many2one("yousentech.booking.package", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="package_id.company_id", store=True, index=True)
    sequence = fields.Integer(default=10)
    service_id = fields.Many2one("yousentech.booking.service", required=True, domain="[('company_id','=',company_id)]")
    quantity = fields.Float(default=1.0, required=True)
    price_unit = fields.Monetary(related="service_id.price", readonly=True)
    subtotal = fields.Monetary(compute="_compute_subtotal", store=True)
    currency_id = fields.Many2one(related="package_id.currency_id", store=True, readonly=True)

    @api.constrains("quantity")
    def _check_quantity(self):
        for line in self:
            if line.quantity<=0:
                raise ValidationError(_("Package service quantity must be greater than zero."))

    @api.depends("quantity","price_unit")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit

class BookingPackage(models.Model):
    _name = "yousentech.booking.package"
    _description = "Booking Package"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self:self.env.company, index=True)
    line_ids = fields.One2many("yousentech.booking.package.line","package_id", string="Services")
    pricing_type = fields.Selection([("fixed","سعر ثابت للباقة"),("services","مجموع الخدمات")], string="طريقة التسعير", default="fixed", required=True)
    fixed_price = fields.Monetary()
    services_total = fields.Monetary(compute="_compute_services_total", store=True)
    price = fields.Monetary(compute="_compute_price", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)

    @api.depends("line_ids.subtotal")
    def _compute_services_total(self):
        for rec in self: rec.services_total=sum(rec.line_ids.mapped("subtotal"))

    @api.depends("pricing_type","fixed_price","services_total")
    def _compute_price(self):
        for rec in self: rec.price=rec.fixed_price if rec.pricing_type=="fixed" else rec.services_total

    @api.constrains("line_ids")
    def _check_lines_company(self):
        for rec in self:
            if rec.line_ids.filtered(lambda l:l.service_id.company_id!=rec.company_id):
                raise ValidationError(_("All package services must belong to the package branch/company."))
