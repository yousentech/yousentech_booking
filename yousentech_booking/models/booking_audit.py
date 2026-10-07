from odoo import fields, models

class BookingAuditLog(models.Model):
    _name = "yousentech.booking.audit.log"
    _description = "Booking Audit Log"
    _order = "create_date desc, id desc"
    _log_access = True

    company_id = fields.Many2one("res.company", required=True, index=True)
    model_name = fields.Char(required=True, index=True)
    record_id = fields.Integer(required=True, index=True)
    action = fields.Selection([("state","State Change"),("cancel","Cancellation"),("reopen","Reopen"),("finance","Finance")], required=True)
    reason = fields.Text()
    user_id = fields.Many2one("res.users", required=True, default=lambda self:self.env.user)
