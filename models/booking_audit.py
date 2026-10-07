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


class BookingAuditMixin(models.AbstractModel):
    _name="yousentech.booking.audit.mixin"
    _description="Booking Audit Mixin"

    audit_log_ids=fields.One2many(
        "yousentech.booking.audit.log",
        compute="_compute_audit_logs",
        string="History",
    )
    audit_log_count=fields.Integer(compute="_compute_audit_logs")

    def _compute_audit_logs(self):
        Audit=self.env["yousentech.booking.audit.log"]
        for rec in self:
            logs=Audit.search([
                ("model_name","=",rec._name),
                ("record_id","=",rec.id),
            ],order="create_date desc,id desc") if rec.id else Audit
            rec.audit_log_ids=logs
            rec.audit_log_count=len(logs)

    def action_view_history(self):
        self.ensure_one()
        return {
            "name":_("Booking History"),
            "type":"ir.actions.act_window",
            "res_model":"yousentech.booking.audit.log",
            "view_mode":"tree,form",
            "domain":[("model_name","=",self._name),("record_id","=",self.id)],
            "context":{"create":False,"delete":False},
        }


class BookingEventAudit(models.Model):
    _name="yousentech.booking.event"
    _inherit=["yousentech.booking.event","yousentech.booking.audit.mixin"]


class StayBookingAudit(models.Model):
    _name="yousentech.stay.booking"
    _inherit=["yousentech.stay.booking","yousentech.booking.audit.mixin"]
