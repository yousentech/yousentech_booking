from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

BOOKING_ACTIVITY_TYPES = [
    ("events", "قاعات ومناسبات"),
    ("stays", "فندقي / إقامة"),
    ("both", "القاعات والإقامة"),
]


class BookingSettings(models.Model):
    _name = "yousentech.booking.settings"
    _description = "إعدادات نظام الحجوزات"
    _rec_name = "company_id"

    company_id = fields.Many2one(
        "res.company",
        string="الشركة / الفرع",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        ondelete="cascade",
    )
    activity_type = fields.Selection(
        BOOKING_ACTIVITY_TYPES,
        string="نوع نشاط الحجز",
        required=True,
    )
    allow_open_stay = fields.Boolean(
        string="السماح بإقامة مفتوحة بدون تاريخ خروج",
        default=False,
        help="عند التفعيل يمكن إنشاء حجز إقامة بدون تاريخ خروج، ويبقى مورد الإقامة محجوزًا للمستقبل حتى تحديد تاريخ الخروج.",
    )

    _sql_constraints = [
        ("booking_settings_company_unique", "unique(company_id)", "يوجد سجل إعدادات لهذه الشركة / الفرع بالفعل."),
    ]

    @api.model
    def action_open_settings(self):
        company = self.env.company
        settings = self.search([("company_id", "=", company.id)], limit=1)
        if not settings:
            settings = self.create({
                "company_id": company.id,
                "activity_type": company.booking_activity_type or "both",
                "allow_open_stay": company.booking_allow_open_stay,
            })
        return {
            "type": "ir.actions.act_window",
            "name": _("إعدادات النظام"),
            "res_model": self._name,
            "res_id": settings.id,
            "view_mode": "form",
            "target": "current",
        }

    @api.model
    def _settings_for_company(self, company):
        settings = self.search([("company_id", "=", company.id)], limit=1)
        if settings:
            return settings
        legacy_activity = company.booking_activity_type
        if not legacy_activity:
            return self.browse()
        return self.create({
            "company_id": company.id,
            "activity_type": legacy_activity,
            "allow_open_stay": company.booking_allow_open_stay,
        })

    @api.constrains("company_id")
    def _check_allowed_company(self):
        for rec in self:
            if rec.company_id not in self.env.companies:
                raise ValidationError(_("لا تملك صلاحية إعداد هذه الشركة / الفرع."))

    def _has_operations(self):
        self.ensure_one()
        return bool(
            self.env["yousentech.booking.event"].sudo().search_count([("company_id", "=", self.company_id.id)])
            or self.env["yousentech.stay.booking"].sudo().search_count([("company_id", "=", self.company_id.id)])
        )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_legacy_company_fields()
        return records

    def write(self, vals):
        if "activity_type" in vals:
            for rec in self:
                if rec.activity_type and vals["activity_type"] != rec.activity_type and rec._has_operations():
                    raise ValidationError(_(
                        "لا يمكن تغيير نوع نشاط الحجز بعد بدء العمليات ووجود حجوزات على الشركة / الفرع."
                    ))
        result = super().write(vals)
        self._sync_legacy_company_fields()
        return result

    def unlink(self):
        for rec in self:
            if rec._has_operations():
                raise ValidationError(_("لا يمكن حذف إعدادات الحجز بعد بدء العمليات."))
        return super().unlink()

    def _sync_legacy_company_fields(self):
        for rec in self:
            rec.company_id.with_context(booking_settings_sync=True).write({
                "booking_activity_type": rec.activity_type,
                "booking_allow_open_stay": rec.allow_open_stay,
            })


class ResCompany(models.Model):
    _inherit = "res.company"

    booking_activity_type = fields.Selection(
        BOOKING_ACTIVITY_TYPES,
        string="نوع نشاط الحجز",
        default=False,
        required=False,
    )
    booking_allow_open_stay = fields.Boolean(
        string="السماح بإقامة مفتوحة بدون تاريخ خروج",
        default=False,
    )

    def write(self, vals):
        protected = {"booking_activity_type", "booking_allow_open_stay"} & set(vals)
        if protected and not self.env.context.get("booking_settings_sync"):
            raise ValidationError(_("يجب تعديل إعدادات الحجز من قائمة «إعدادات النظام» داخل تطبيق الحجوزات."))
        return super().write(vals)
