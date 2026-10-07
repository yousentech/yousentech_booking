from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

BLOCKING_STATES = ("hold", "confirmed", "checked_in", "checked_out")

class StayBooking(models.Model):
    _name = "yousentech.stay.booking"
    _description = "Stay Booking"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "checkin_date desc, id desc"

    name = fields.Char(default="New", readonly=True, copy=False, index=True)
    company_id = fields.Many2one("res.company", string="Branch", required=True, default=lambda self: self.env.company, index=True, tracking=True)
    partner_id = fields.Many2one("res.partner", required=True, tracking=True)
    resource_id = fields.Many2one("yousentech.stay.resource", required=True, domain="[('company_id','=',company_id)]", tracking=True)
    checkin_date = fields.Date(required=True, index=True, tracking=True)
    checkout_date = fields.Date(required=True, index=True, tracking=True)
    state = fields.Selection([("draft","Draft"),("hold","Hold"),("confirmed","Confirmed"),("checked_in","Checked In"),("checked_out","Checked Out"),("cancelled","Cancelled")], default="draft", required=True, tracking=True, index=True)
    amount_total = fields.Monetary(tracking=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)

    @api.constrains("checkin_date","checkout_date")
    def _check_dates(self):
        for rec in self:
            if rec.checkin_date and rec.checkout_date and rec.checkout_date <= rec.checkin_date:
                raise ValidationError(_("Checkout must be after check-in."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("yousentech.stay.booking") or "New"
        records = super().create(vals_list)
        records._check_company_integrity()
        records._check_availability(lock=True)
        return records

    def write(self, vals):
        result = super().write(vals)
        if {"company_id","resource_id","checkin_date","checkout_date","state"} & set(vals):
            self._check_company_integrity()
            self._check_availability(lock=True)
        return result

    def _check_company_integrity(self):
        for rec in self:
            if rec.company_id not in self.env.companies:
                raise ValidationError(_("You are not allowed to operate this branch/company."))
            if rec.resource_id and rec.resource_id.company_id != rec.company_id:
                raise ValidationError(_("The stay resource must belong to the booking branch/company."))

    def _check_availability(self, lock=False):
        for rec in self.filtered(lambda r: r.state in BLOCKING_STATES and r.resource_id and r.checkin_date and r.checkout_date):
            if lock:
                self.env.cr.execute("SELECT id FROM yousentech_stay_resource WHERE id = %s FOR UPDATE", [rec.resource_id.id])
            conflict = self.search([("id","!=",rec.id),("company_id","=",rec.company_id.id),("resource_id","=",rec.resource_id.id),("state","in",BLOCKING_STATES),("checkin_date","<",rec.checkout_date),("checkout_date",">",rec.checkin_date)], limit=1)
            if conflict:
                raise ValidationError(_("The resource is not available for this stay; conflict with %s.") % conflict.display_name)
