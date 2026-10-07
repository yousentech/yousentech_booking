from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


BOOKING_ACTIVITY_TYPES = [
    ("events", "قاعات ومناسبات"),
    ("stays", "فندقي / إقامة"),
    ("both", "القاعات والإقامة"),
]


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
        help="عند التفعيل يمكن إنشاء حجز إقامة بدون تاريخ خروج. يبقى مورد الإقامة محجوزًا من تاريخ الدخول حتى تحديد تاريخ الخروج.",
    )

    def write(self, vals):
        if "booking_activity_type" in vals:
            new_type = vals["booking_activity_type"]
            for company in self:
                old_type = company.booking_activity_type
                if old_type and old_type != new_type:
                    has_events = bool(self.env["yousentech.booking.event"].sudo().search_count([
                        ("company_id", "=", company.id),
                    ]))
                    has_stays = bool(self.env["yousentech.stay.booking"].sudo().search_count([
                        ("company_id", "=", company.id),
                    ]))
                    if has_events or has_stays:
                        raise ValidationError(_(
                            "لا يمكن تغيير نوع نشاط الحجز بعد بدء العمليات ووجود حجوزات على الشركة / الفرع. "
                            "نوع النشاط الحالي سيبقى كما هو حفاظًا على سلامة البيانات."
                        ))
        return super().write(vals)


class BookingActivitySetup(models.TransientModel):
    _name = "yousentech.booking.activity.setup"
    _description = "تهيئة نشاط الحجز"

    company_id = fields.Many2one(
        "res.company",
        string="الشركة / الفرع",
        required=True,
        default=lambda self: self.env.company,
    )
    activity_type = fields.Selection(
        BOOKING_ACTIVITY_TYPES,
        string="نوع نشاط الحجز",
        required=True,
    )
    allow_open_stay = fields.Boolean(
        string="السماح بإقامة مفتوحة بدون تاريخ خروج",
    )

    @api.onchange("company_id")
    def _onchange_company_id(self):
        self.activity_type = self.company_id.booking_activity_type if self.company_id else False
        self.allow_open_stay = self.company_id.booking_allow_open_stay if self.company_id else False

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        company = self.env.company
        if "company_id" in fields_list:
            values["company_id"] = company.id
        if "activity_type" in fields_list:
            values["activity_type"] = company.booking_activity_type
        if "allow_open_stay" in fields_list:
            values["allow_open_stay"] = company.booking_allow_open_stay
        return values

    def action_save(self):
        self.ensure_one()
        if not self.env.user.has_group("yousentech_booking.group_booking_manager"):
            raise ValidationError(_("هذه العملية متاحة لمدير الحجوزات فقط."))
        if self.company_id not in self.env.companies:
            raise ValidationError(_("لا تملك صلاحية تهيئة هذه الشركة / الفرع."))
        self.company_id.write({
            "booking_activity_type": self.activity_type,
            "booking_allow_open_stay": self.allow_open_stay,
        })
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("تم حفظ الإعداد"),
                "message": _("تم اعتماد نوع نشاط الحجز للشركة / الفرع."),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
