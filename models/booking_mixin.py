from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class BookingCompanyMixin(models.AbstractModel):
    _name = "yousentech.booking.company.mixin"
    _description = "Booking Company Mixin"

    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)

    def _ensure_allowed_company(self):
        for rec in self:
            if rec.company_id not in self.env.companies:
                raise ValidationError(_("You are not allowed to operate this branch/company."))

    @api.model
    def _lock_record(self, table, record_id):
        if record_id:
            self.env.cr.execute('SELECT id FROM "%s" WHERE id = %%s FOR UPDATE' % table, [record_id])
