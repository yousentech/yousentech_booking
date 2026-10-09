from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class StayResource(models.Model):
    _name = "yousentech.stay.resource"
    _description = "Stay Resource"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    floor_name = fields.Char(string="الطابق", default="غير محدد", index=True, help="اسم أو رقم الطابق لتجميع الغرف في مخطط الإشغال.")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", string="الشركة / الفرع", required=True, default=lambda self: self.env.company, index=True)
    resource_type = fields.Selection([("room","غرفة"),("suite","جناح"),("apartment","شقة"),("chalet","شاليه")], string="نوع المورد", default="room", required=True)
    capacity = fields.Integer(default=2)
    housekeeping_state = fields.Selection([("unknown","غير محددة"),("clean","نظيفة وجاهزة"),("dirty","تحتاج تنظيفًا"),("inspection","بانتظار الفحص")], string="حالة التجهيز", default="unknown", required=True)
    out_of_service_type = fields.Selection([("maintenance","صيانة"),("blocked","موقوفة عن البيع")], string="حالة الإيقاف")
    out_of_service_from = fields.Date(string="بداية الإيقاف")
    out_of_service_to = fields.Date(string="نهاية الإيقاف (غير شاملة)")
    out_of_service_reason = fields.Char(string="سبب الإيقاف")

    @api.constrains("out_of_service_type","out_of_service_from","out_of_service_to")
    def _check_closure(self):
        for rec in self:
            if rec.out_of_service_type and not rec.out_of_service_from:
                raise ValidationError(_("حدد تاريخ بداية الإيقاف."))
            if rec.out_of_service_to and (not rec.out_of_service_from or rec.out_of_service_to <= rec.out_of_service_from):
                raise ValidationError(_("تاريخ النهاية يجب أن يكون بعد البداية."))

    def _is_out_of_service(self, start, end):
        self.ensure_one()
        return bool(self.out_of_service_type and self.out_of_service_from and self.out_of_service_from < (end or fields.Date.to_date("9999-12-31")) and (not self.out_of_service_to or self.out_of_service_to > start))

    product_id = fields.Many2one("product.product", string="منتج الفوترة", domain="[('sale_ok','=',True)]")
    nightly_price = fields.Monetary()
    currency_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)

    @api.constrains("product_id", "company_id")
    def _check_product_company(self):
        for rec in self:
            if rec.product_id.company_id and rec.product_id.company_id != rec.company_id:
                raise ValidationError(_("منتج الفوترة يجب أن يتبع نفس شركة / فرع مورد الإقامة."))
