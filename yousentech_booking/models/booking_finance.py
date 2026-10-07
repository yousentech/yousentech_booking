from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

POLICIES=[("manual","Manual"),("full","Full on Confirmation"),("deposit","Deposit then Final"),("schedule","Installment Schedule")]
INVOICE_KINDS=[("manual","Manual"),("full","Full"),("deposit","Deposit"),("balance","Balance"),("installment","Installment"),("refund","Refund")]
EVENT_INVOICE_STATES=("confirmed","preparing","event","completed")
STAY_INVOICE_STATES=("confirmed","checked_in","checked_out")

class AccountMove(models.Model):
    _inherit="account.move"
    yousentech_event_booking_id=fields.Many2one("yousentech.booking.event",index=True,copy=False,ondelete="restrict")
    yousentech_stay_booking_id=fields.Many2one("yousentech.stay.booking",index=True,copy=False,ondelete="restrict")
    yousentech_schedule_id=fields.Many2one("yousentech.booking.payment.schedule",index=True,copy=False,ondelete="restrict")
    yousentech_snapshot_id=fields.Many2one("yousentech.booking.commercial.snapshot",index=True,copy=False,readonly=True,ondelete="restrict")
    yousentech_booking_invoice_kind=fields.Selection(INVOICE_KINDS,copy=False,index=True)

    @api.model_create_multi
    def create(self,vals_list):
        for vals in vals_list:
            reversed_id=vals.get("reversed_entry_id")
            if reversed_id:
                source=self.browse(reversed_id)
                if source.exists():
                    vals.setdefault("yousentech_event_booking_id",source.yousentech_event_booking_id.id)
                    vals.setdefault("yousentech_stay_booking_id",source.yousentech_stay_booking_id.id)
                    vals.setdefault("yousentech_snapshot_id",source.yousentech_snapshot_id.id)
                    if vals.get("move_type")=="out_refund":
                        vals.setdefault("yousentech_booking_invoice_kind","refund")
        return super().create(vals_list)

    @api.constrains("yousentech_event_booking_id","yousentech_stay_booking_id","yousentech_snapshot_id","company_id")
    def _check_booking_links(self):
        for move in self:
            if move.yousentech_event_booking_id and move.yousentech_stay_booking_id:
                raise ValidationError(_("An accounting document cannot belong to both an event and a stay booking."))
            booking=move.yousentech_event_booking_id or move.yousentech_stay_booking_id
            if booking and booking.company_id!=move.company_id:
                raise ValidationError(_("Accounting document company must match booking company."))
            snapshot=move.yousentech_snapshot_id
            if snapshot and booking:
                snapshot_booking=snapshot.event_booking_id or snapshot.stay_booking_id
                if snapshot_booking!=booking:
                    raise ValidationError(_("Commercial snapshot must belong to the same booking as the accounting document."))

class BookingFinanceMixin(models.AbstractModel):
    _name="yousentech.booking.finance.mixin"
    _description="Booking Finance Mixin"
    invoice_policy=fields.Selection(POLICIES,default="manual",required=True,tracking=True)
    deposit_percent=fields.Float(default=30.0)
    amount_invoiced=fields.Monetary(compute="_compute_finance")
    amount_to_invoice=fields.Monetary(compute="_compute_finance")
    amount_paid=fields.Monetary(compute="_compute_finance")
    amount_due=fields.Monetary(compute="_compute_finance")
    amount_remaining=fields.Monetary(compute="_compute_finance")
    finance_state=fields.Selection([("not_invoiced","Not Invoiced"),("invoiced","Invoiced"),("partial","Partially Paid"),("paid","Paid")],compute="_compute_finance")

    def _compute_finance(self):
        for rec in self:
            posted=rec.invoice_ids.filtered(lambda m:m.state=="posted" and m.move_type in ("out_invoice","out_refund"))
            invoices=posted.filtered(lambda m:m.move_type=="out_invoice")
            refunds=posted.filtered(lambda m:m.move_type=="out_refund")
            invoiced=sum(invoices.mapped("amount_total"))-sum(refunds.mapped("amount_total"))
            invoice_residual=sum(invoices.mapped("amount_residual"))
            refund_residual=sum(refunds.mapped("amount_residual"))
            paid=sum((m.amount_total-m.amount_residual) for m in invoices)-sum((m.amount_total-m.amount_residual) for m in refunds)
            due=max(invoice_residual-refund_residual,0.0)
            rec.amount_invoiced=max(invoiced,0.0)
            active_coverage=sum(rec.invoice_ids.filtered(lambda m:m.state!="cancel" and m.move_type=="out_invoice").mapped("amount_total"))
            rec.amount_to_invoice=max(rec.amount_total-active_coverage,0.0)
            rec.amount_paid=max(paid,0.0)
            rec.amount_due=due
            rec.amount_remaining=due
            if not posted:
                rec.finance_state="not_invoiced"
            elif rec.currency_id.is_zero(due) and rec.currency_id.is_zero(rec.amount_to_invoice):
                rec.finance_state="paid"
            elif rec.amount_paid>0:
                rec.finance_state="partial"
            else:
                rec.finance_state="invoiced"

    @api.constrains("deposit_percent")
    def _check_deposit(self):
        for rec in self:
            if not 0<=rec.deposit_percent<=100:
                raise ValidationError(_("Deposit percentage must be between 0 and 100."))

    def _sale_journal(self):
        self.ensure_one()
        journal=self.env["account.journal"].with_company(self.company_id).search([("company_id","=",self.company_id.id),("type","=","sale")],limit=1)
        if not journal:
            raise UserError(_("Configure a sales journal for this branch/company."))
        return journal

    def _booking_link(self):
        return {"yousentech_event_booking_id":self.id} if self._name=="yousentech.booking.event" else {"yousentech_stay_booking_id":self.id}

    def _latest_snapshot(self):
        self.ensure_one()
        snapshot=self.commercial_snapshot_ids.sorted(lambda s:(s.revision,s.id),reverse=True)[:1]
        if not snapshot:
            raise UserError(_("Confirm the commercial terms before creating an invoice."))
        return snapshot

    def _invoice_lines(self,ratio=1.0,label=None):
        self.ensure_one()
        if ratio<=0:
            raise UserError(_("Invoice ratio must be greater than zero."))
        if self._name=="yousentech.booking.event":
            lines=[(0,0,{"name":label or _("Hall: %s")%self.hall_id.display_name,"quantity":1.0,"price_unit":self.hall_id.list_price*ratio})]
            if self.package_id and self.package_id.pricing_type=="fixed":\n                lines.append((0,0,{"name":_("Package: %s")%self.package_id.display_name,"quantity":1.0,"price_unit":self.package_id.price*ratio}))\n            else:\n                lines += [(0,0,{"product_id":l.service_id.product_id.id,"name":l.service_id.display_name,"quantity":l.quantity,"price_unit":l.price_unit*ratio,"tax_ids":[(6,0,l.service_id.tax_ids.ids)]}) for l in self.service_line_ids]
            if self.discount_amount:
                lines.append((0,0,{"name":_("Booking discount"),"quantity":1.0,"price_unit":-self.discount_amount*ratio}))
            return lines
        lines=[(0,0,{"name":label or _("Stay: %s")%self.resource_id.display_name,"quantity":self.nights or 1,"price_unit":self.nightly_price*ratio})]
        lines += [(0,0,{"product_id":l.addon_id.product_id.id,"name":l.addon_id.display_name,"quantity":l.quantity*(self.nights if l.addon_id.charge_type=="night" else 1),"price_unit":l.price_unit*ratio,"tax_ids":[(6,0,l.addon_id.tax_ids.ids)]}) for l in self.addon_line_ids]
        return lines

    def _create_invoice(self,ratio=1.0,label=None,schedule=None,kind="manual"):
        self.ensure_one()
        allowed=EVENT_INVOICE_STATES if self._name=="yousentech.booking.event" else STAY_INVOICE_STATES
        if self.state not in allowed:
            raise UserError(_("Invoices can only be created after the booking is confirmed."))
        if not self.partner_id:
            raise UserError(_("A customer is required."))
        if schedule and schedule.invoice_id and schedule.invoice_id.state!="cancel":
            raise UserError(_("This installment already has an active invoice."))
        if self.amount_total<=0:
            raise UserError(_("Cannot create an invoice for a zero-total booking."))
        active=self.invoice_ids.filtered(lambda m:m.state!="cancel" and m.move_type=="out_invoice")
        if kind in ("full","deposit","balance") and active.filtered(lambda m:m.yousentech_booking_invoice_kind==kind):
            raise UserError(_("This invoice stage already has an active invoice."))
        if kind=="manual" and active:
            raise UserError(_("This booking already has an active invoice. Use the applicable balance/installment action."))
        snapshot=self._latest_snapshot()
        vals={"move_type":"out_invoice","company_id":self.company_id.id,"journal_id":self._sale_journal().id,"partner_id":self.partner_id.id,"invoice_origin":self.name,"invoice_line_ids":self._invoice_lines(ratio,label),"yousentech_snapshot_id":snapshot.id,"yousentech_booking_invoice_kind":kind,**self._booking_link()}
        if schedule:
            vals["yousentech_schedule_id"]=schedule.id
        move=self.env["account.move"].with_company(self.company_id).create(vals)
        if schedule:
            schedule.with_context(booking_schedule_system_write=True).write({"invoice_id":move.id})
        self._audit("finance",_("Draft %s invoice created.")%kind)
        return move

    def action_create_invoice(self):
        self.ensure_one()
        move=self._create_invoice(kind="manual")
        return {"type":"ir.actions.act_window","res_model":"account.move","res_id":move.id,"view_mode":"form","target":"current"}

    def _apply_confirmation_invoice_policy(self):
        for rec in self:
            active=rec.invoice_ids.filtered(lambda m:m.state!="cancel" and m.move_type=="out_invoice")
            if active:
                continue
            if rec.invoice_policy=="full":
                rec._create_invoice(kind="full")
            elif rec.invoice_policy=="deposit":
                if rec.deposit_percent<=0:
                    raise UserError(_("Deposit percentage is required."))
                rec._create_invoice(rec.deposit_percent/100.0,_("Booking deposit"),kind="deposit")
            elif rec.invoice_policy=="schedule":
                lines=rec.payment_schedule_ids.filtered(lambda l:l.state!="cancelled")
                total=sum(lines.mapped("amount"))
                if not rec.currency_id.is_zero(total-rec.amount_total):
                    raise UserError(_("Payment schedule total must equal booking total."))
                if rec.currency_id.is_zero(rec.amount_total):
                    raise UserError(_("Cannot invoice a zero-total booking by schedule."))
                for line in lines.filtered(lambda l:l.state=="pending"):
                    rec._create_invoice(line.amount/rec.amount_total,line.name,line,kind="installment")

    def _check_finance_before_cancel(self):
        for rec in self:
            posted=rec.invoice_ids.filtered(lambda m:m.state=="posted" and m.move_type in ("out_invoice","out_refund"))
            if not posted:
                continue
            invoices=posted.filtered(lambda m:m.move_type=="out_invoice")
            refunds=posted.filtered(lambda m:m.move_type=="out_refund")
            net_total=sum(invoices.mapped("amount_total"))-sum(refunds.mapped("amount_total"))
            unsettled=posted.filtered(lambda m:not rec.currency_id.is_zero(m.amount_residual))
            if not rec.currency_id.is_zero(net_total) or unsettled:
                raise UserError(_("Accounting must be fully reversed/refunded and reconciled before cancelling this booking."))

    def action_create_credit_note(self):
        self.ensure_one()
        if not self.env.user.has_group("yousentech_booking.group_booking_manager"):
            raise UserError(_("Only a booking manager can reverse booking invoices."))
        posted=self.invoice_ids.filtered(lambda m:m.state=="posted" and m.move_type=="out_invoice" and m.payment_state!="reversed")
        if not posted:
            raise UserError(_("There is no posted customer invoice to reverse."))
        return {"name":_("Reverse Booking Invoice"),"type":"ir.actions.act_window","res_model":"account.move.reversal","view_mode":"form","target":"new","context":{"active_model":"account.move","active_ids":posted.ids,"default_reason":_("Booking %s cancellation/refund")%self.name}}

    def action_create_final_invoice(self):
        self.ensure_one()
        if self.invoice_policy!="deposit":
            raise UserError(_("Final invoice is only available for deposit policy."))
        active=self.invoice_ids.filtered(lambda m:m.state!="cancel" and m.move_type=="out_invoice")
        deposits=active.filtered(lambda m:m.yousentech_booking_invoice_kind=="deposit")
        if not deposits:
            raise UserError(_("Create the deposit invoice first."))
        if active.filtered(lambda m:m.yousentech_booking_invoice_kind=="balance"):
            raise UserError(_("The balance invoice already exists."))
        already=sum(active.mapped("amount_total"))
        remaining=self.amount_total-already
        if self.currency_id.is_zero(remaining) or remaining<0:
            raise UserError(_("Nothing remains to invoice."))
        ratio=remaining/self.amount_total
        move=self._create_invoice(ratio,_("Booking balance"),kind="balance")
        return {"type":"ir.actions.act_window","res_model":"account.move","res_id":move.id,"view_mode":"form","target":"current"}

    def _check_unlink_finance(self):
        for rec in self:
            if rec.invoice_ids:
                raise UserError(_("A booking linked to accounting documents cannot be deleted."))
            if rec.payment_schedule_ids:
                raise UserError(_("Delete the booking payment schedule before deleting this booking."))
            if rec.commercial_snapshot_ids:
                raise UserError(_("A booking with confirmed commercial history cannot be deleted."))

class BookingEvent(models.Model):
    _inherit=["yousentech.booking.event","yousentech.booking.finance.mixin"]
    invoice_ids=fields.One2many("account.move","yousentech_event_booking_id",string="Invoices")
    payment_schedule_ids=fields.One2many("yousentech.booking.payment.schedule","event_booking_id")
    invoice_count=fields.Integer(compute="_compute_invoice_count")
    def _compute_invoice_count(self):
        for rec in self: rec.invoice_count=len(rec.invoice_ids)
    def unlink(self):
        self._check_unlink_finance()
        if self.filtered(lambda r:r.state not in ("draft","cancelled")):
            raise UserError(_("Only draft or cancelled bookings can be deleted."))
        return super().unlink()

class StayBooking(models.Model):
    _inherit=["yousentech.stay.booking","yousentech.booking.finance.mixin"]
    invoice_ids=fields.One2many("account.move","yousentech_stay_booking_id",string="Invoices")
    payment_schedule_ids=fields.One2many("yousentech.booking.payment.schedule","stay_booking_id")
    invoice_count=fields.Integer(compute="_compute_invoice_count")
    def _compute_invoice_count(self):
        for rec in self: rec.invoice_count=len(rec.invoice_ids)
    def unlink(self):
        self._check_unlink_finance()
        if self.filtered(lambda r:r.state not in ("draft","cancelled")):
            raise UserError(_("Only draft or cancelled bookings can be deleted."))
        return super().unlink()
