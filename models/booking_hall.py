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

class BookingHallPeriodPrice(models.Model):
    _name = "yousentech.booking.hall.period.price"
    _description = "Hall Price by Booking Period"
    _order = "period_id, id"
    hall_id = fields.Many2one("yousentech.booking.hall", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="hall_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="hall_id.currency_id", readonly=True)
    period_id = fields.Many2one("yousentech.booking.period", required=True, domain="[('company_id', '=', company_id)]")
    price = fields.Monetary(required=True)

    _sql_constraints = [
        ("unique_hall_period", "unique(hall_id,period_id)", "لا يمكن تكرار نفس الفترة في أسعار القاعة."),
        ("positive_period_price", "CHECK(price >= 0)", "سعر الفترة لا يمكن أن يكون سالباً."),
    ]

    @api.constrains("period_id", "hall_id")
    def _check_company(self):
        for rec in self:
            if rec.period_id.company_id != rec.hall_id.company_id:
                raise ValidationError(_("Hall and period must belong to the same company."))

class BookingHallPeriodPricing(models.Model):
    _inherit = "yousentech.booking.hall"
    tax_id = fields.Many2one("account.tax", string="ضريبة القاعة", domain="[('company_id','=',company_id),('type_tax_use','in',('sale','none'))]")
    period_price_ids = fields.One2many("yousentech.booking.hall.period.price", "hall_id", string="أسعار الفترات")

    @api.constrains("tax_id", "company_id")
    def _check_hall_tax_company(self):
        for hall in self:
            if hall.tax_id and hall.tax_id.company_id != hall.company_id:
                raise ValidationError(_("Hall tax must belong to the same company."))
