from odoo import api, fields, models, _
from odoo.exceptions import AccessError

class BookingAuditLog(models.Model):
    _name="yousentech.booking.audit.log"
    _description="Booking Audit Log"
    _order="create_date desc, id desc"
    _log_access=True

    company_id=fields.Many2one("res.company",required=True,index=True)
    model_name=fields.Char(required=True,index=True)
    record_id=fields.Integer(required=True,index=True)
    action=fields.Selection([("create","Created"),("update","Updated"),("state","State Change"),("cancel","Cancellation"),("reopen","Reopen"),("finance","Finance")],required=True)
    reason=fields.Text()
    details=fields.Text(readonly=True)
    user_id=fields.Many2one("res.users",required=True,default=lambda self:self.env.user)

    @api.model_create_multi
    def create(self,vals_list):
        if not self.env.su and not self.env.context.get("booking_audit_system_create"):
            raise AccessError(_("Booking audit entries are system generated."))
        return super().create(vals_list)

    def write(self,vals):
        raise AccessError(_("Booking audit entries are immutable."))

    def unlink(self):
        raise AccessError(_("Booking audit entries cannot be deleted."))
