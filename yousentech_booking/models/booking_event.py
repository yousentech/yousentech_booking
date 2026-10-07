from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

BLOCKING_STATES = ("hold", "confirmed", "preparing", "event", "completed")

class BookingEvent(models.Model):
    _name = "yousentech.booking.event"
    _description = "Event Booking"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "booking_date desc, id desc"

    name = fields.Char(default="New", readonly=True, copy=False, index=True)
    company_id = fields.Many2one("res.company", string="Branch", required=True, default=lambda self: self.env.company, index=True, tracking=True)
    partner_id = fields.Many2one("res.partner", required=True, tracking=True)
    booking_date = fields.Date(required=True, index=True, tracking=True)
    hall_id = fields.Many2one("yousentech.booking.hall", required=True, domain="[('company_id', '=', company_id)]", tracking=True)
    period_ids = fields.Many2many("yousentech.booking.period", string="Periods", domain="[('company_id', '=', company_id)]")
    state = fields.Selection([("draft","Draft"),("hold","Hold"),("confirmed","Confirmed"),("preparing","Preparing"),("event","Event"),("completed","Completed"),("cancelled","Cancelled")], default="draft", required=True, tracking=True, index=True)
    amount_total = fields.Monetary(tracking=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("yousentech.booking.event") or "New"
        records = super().create(vals_list)
        records._check_company_integrity()
        records._check_availability(lock=True)
        return records

    def write(self, vals):
        result = super().write(vals)
        if {"company_id","booking_date","hall_id","period_ids","state"} & set(vals):
            self._check_company_integrity()
            self._check_availability(lock=True)
        return result

    def _check_company_integrity(self):
        for rec in self:
            if rec.company_id not in self.env.companies:
                raise ValidationError(_("You are not allowed to operate this branch/company."))
            if rec.hall_id and rec.hall_id.company_id != rec.company_id:
                raise ValidationError(_("The hall must belong to the booking branch/company."))
            if rec.period_ids.filtered(lambda p: p.company_id != rec.company_id):
                raise ValidationError(_("All periods must belong to the booking branch/company."))

    def _check_availability(self, lock=False):
        for rec in self.filtered(lambda r: r.state in BLOCKING_STATES and r.hall_id and r.booking_date and r.period_ids):
            if lock:
                self.env.cr.execute("SELECT id FROM yousentech_booking_hall WHERE id = %s FOR UPDATE", [rec.hall_id.id])
            conflict = self.search([("id","!=",rec.id),("company_id","=",rec.company_id.id),("hall_id","=",rec.hall_id.id),("booking_date","=",rec.booking_date),("state","in",BLOCKING_STATES),("period_ids","in",rec.period_ids.ids)], limit=1)
            if conflict:
                raise ValidationError(_("The hall/period is already booked by %s.") % conflict.display_name)
