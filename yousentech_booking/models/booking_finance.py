from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

POLICIES=[("manual","Manual"),("full","Full on Confirmation"),("deposit","Deposit then Final"),("schedule","Installment Schedule")]

class AccountMove(models.Model):
    _inherit="account.move"
    yousentech_event_booking_id=fields.Many2one("yousentech.booking.event",index=True,copy=False)
    yousentech_stay_booking_id=fields.Many2one("yousentech.stay.booking",index=True,copy=False)
    yousentech_schedule_id=fields.Many2one("yousentech.booking.payment.schedule",index=True,copy=False)

class BookingFinanceMixin(models.AbstractModel):
    _name="yousentech.booking.finance.mixin"
    _description="Booking Finance Mixin"
    invoice_policy=fields.Selection(POLICIES,default="manual",required=True,tracking=True)
    deposit_percent=fields.Float(default=30.0)
    amount_invoiced=fields.Monetary(compute="_compute_finance")
    amount_paid=fields.Monetary(compute="_compute_finance")
    amount_remaining=fields.Monetary(compute="_compute_finance")
    finance_state=fields.Selection([("not_invoiced","Not Invoiced"),("invoiced","Invoiced"),("partial","Partially Paid"),("paid","Paid")],compute="_compute_finance")

    def _compute_finance(self):
        for rec in self:
            moves=rec.invoice_ids.filtered(lambda m:m.state!="cancel")
            invoices=moves.filtered(lambda m:m.move_type=="out_invoice")
            refunds=moves.filtered(lambda m:m.move_type=="out_refund")
            invoiced=sum(invoices.mapped("amount_total"))-sum(refunds.mapped("amount_total"))
            residual=sum(invoices.mapped("amount_residual"))-sum(refunds.mapped("amount_residual"))
            rec.amount_invoiced=invoiced
            rec.amount_remaining=max(residual,0.0)
            rec.amount_paid=max(invoiced-residual,0.0)
            rec.finance_state="not_invoiced" if not moves else ("paid" if rec.currency_id.is_zero(rec.amount_remaining) else "partial" if rec.amount_paid else "invoiced")

    @api.constrains("deposit_percent")
    def _check_deposit(self):
        for rec in self:
            if not 0<=rec.deposit_percent<=100: raise ValidationError(_("Deposit percentage must be between 0 and 100."))

    def _sale_journal(self):
        self.ensure_one()
        journal=self.env["account.journal"].with_company(self.company_id).search([("company_id","=",self.company_id.id),("type","=","sale")],limit=1)
        if not journal: raise UserError(_("Configure a sales journal for this branch/company."))
        return journal

    def _booking_link(self):
        return {"yousentech_event_booking_id":self.id} if self._name=="yousentech.booking.event" else {"yousentech_stay_booking_id":self.id}

    def _invoice_lines(self):
        self.ensure_one()
        if self._name=="yousentech.booking.event":
            lines=[(0,0,{"name":_("Hall: %s")%self.hall_id.display_name,"quantity":1.0,"price_unit":self.hall_id.list_price})]
            lines += [(0,0,{"product_id":l.service_id.product_id.id,"name":l.service_id.display_name,"quantity":l.quantity,"price_unit":l.price_unit,"tax_ids":[(6,0,l.service_id.tax_ids.ids)]}) for l in self.service_line_ids]
            if self.discount_amount: lines.append((0,0,{"name":_("Booking discount"),"quantity":1.0,"price_unit":-self.discount_amount}))
            return lines
        lines=[(0,0,{"name":_("Stay: %s")%self.resource_id.display_name,"quantity":self.nights or 1,"price_unit":self.nightly_price})]
        lines += [(0,0,{"product_id":l.addon_id.product_id.id,"name":l.addon_id.display_name,"quantity":l.quantity,"price_unit":l.price_unit,"tax_ids":[(6,0,l.addon_id.tax_ids.ids)]}) for l in self.addon_line_ids]
        return lines

    def _create_invoice(self):
        self.ensure_one()
        if not self.partner_id: raise UserError(_("A customer is required."))
        move=self.env["account.move"].with_company(self.company_id).create({"move_type":"out_invoice","company_id":self.company_id.id,"journal_id":self._sale_journal().id,"partner_id":self.partner_id.id,"invoice_origin":self.name,"invoice_line_ids":self._invoice_lines(),**self._booking_link()})
        self._audit("finance",_("Draft invoice created."))
        return move

    def action_create_invoice(self):
        self.ensure_one()
        move=self._create_invoice()
        return {"type":"ir.actions.act_window","res_model":"account.move","res_id":move.id,"view_mode":"form","target":"current"}

class BookingEvent(models.Model):
    _inherit=["yousentech.booking.event","yousentech.booking.finance.mixin"]
    invoice_ids=fields.One2many("account.move","yousentech_event_booking_id",string="Invoices")
    payment_schedule_ids=fields.One2many("yousentech.booking.payment.schedule","event_booking_id")
    invoice_count=fields.Integer(compute="_compute_invoice_count")
    def _compute_invoice_count(self):
        for rec in self: rec.invoice_count=len(rec.invoice_ids)

class StayBooking(models.Model):
    _inherit=["yousentech.stay.booking","yousentech.booking.finance.mixin"]
    invoice_ids=fields.One2many("account.move","yousentech_stay_booking_id",string="Invoices")
    payment_schedule_ids=fields.One2many("yousentech.booking.payment.schedule","stay_booking_id")
    invoice_count=fields.Integer(compute="_compute_invoice_count")
    def _compute_invoice_count(self):
        for rec in self: rec.invoice_count=len(rec.invoice_ids)
