from odoo import fields, models, _
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = "account.move"
    yousentech_event_booking_id = fields.Many2one("yousentech.booking.event", index=True, copy=False)
    yousentech_stay_booking_id = fields.Many2one("yousentech.stay.booking", index=True, copy=False)

class BookingEvent(models.Model):
    _inherit = "yousentech.booking.event"
    invoice_ids = fields.One2many("account.move", "yousentech_event_booking_id", string="Invoices")
    invoice_count = fields.Integer(compute="_compute_invoice_count")
    def _compute_invoice_count(self):
        for rec in self: rec.invoice_count = len(rec.invoice_ids)
    def action_create_invoice(self):
        self.ensure_one()
        if not self.partner_id: raise UserError(_("A customer is required."))
        journal = self.env["account.journal"].search([("company_id","=",self.company_id.id),("type","=","sale")], limit=1)
        if not journal: raise UserError(_("Configure a sales journal for this branch/company."))
        move = self.env["account.move"].with_company(self.company_id).create({"move_type":"out_invoice","company_id":self.company_id.id,"journal_id":journal.id,"partner_id":self.partner_id.id,"invoice_origin":self.name,"yousentech_event_booking_id":self.id})
        return {"type":"ir.actions.act_window","res_model":"account.move","res_id":move.id,"view_mode":"form","target":"current"}

class StayBooking(models.Model):
    _inherit = "yousentech.stay.booking"
    invoice_ids = fields.One2many("account.move", "yousentech_stay_booking_id", string="Invoices")
    invoice_count = fields.Integer(compute="_compute_invoice_count")
    def _compute_invoice_count(self):
        for rec in self: rec.invoice_count = len(rec.invoice_ids)
