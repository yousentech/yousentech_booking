from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class BookingHoliday(models.Model):
    _name = "yousentech.booking.holiday"
    _description = "Booking Calendar Holiday"
    _order = "date, name"

    name = fields.Char(string="اسم الإجازة", required=True)
    date = fields.Date(string="تاريخ الإجازة", required=True, index=True)
    company_id = fields.Many2one(
        "res.company", string="الشركة / الفرع", required=True,
        default=lambda self: self.env.company, index=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("holiday_name_date_company_unique", "unique(name, date, company_id)",
         "هذه الإجازة مسجلة مسبقاً في نفس التاريخ والشركة."),
    ]
