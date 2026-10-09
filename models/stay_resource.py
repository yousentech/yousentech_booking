from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class StayResource(models.Model):
    _name = "yousentech.stay.resource"
    _description = "Stay Resource"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    floor_id = fields.Many2one("yousentech.stay.floor", string="الطابق", index=True, ondelete="restrict", check_company=True)
    floor_name = fields.Char(string="اسم الطابق السابق", index=True, help="للتوافق مع بيانات الطوابق القديمة.")

    @api.onchange("floor_id")
    def _onchange_floor_id(self):
        if self.floor_id:
            self.floor_name = self.floor_id.name

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("floor_id"):
                vals["floor_name"] = self.env["yousentech.stay.floor"].browse(vals["floor_id"]).name
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("floor_id"):
            vals = dict(vals, floor_name=self.env["yousentech.stay.floor"].browse(vals["floor_id"]).name)
        return super().write(vals)

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

    @api.constrains("out_of_service_type","out_of_service_from","out_of_service_to")
    def _check_closure_bookings(self):
        for rec in self:
            if not rec.out_of_service_type or not rec.out_of_service_from:
                continue
            domain = [("resource_id","=",rec.id),("state","in",["hold","confirmed","checked_in","checked_out"]),
                      "|",("checkout_date","=",False),("checkout_date",">",rec.out_of_service_from)]
            if rec.out_of_service_to:
                domain.append(("checkin_date","<",rec.out_of_service_to))
            if self.env["yousentech.stay.booking"].search(domain,limit=1):
                raise ValidationError(_("لا يمكن إيقاف غرفة لديها حجز متعارض مع فترة الإيقاف."))

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
