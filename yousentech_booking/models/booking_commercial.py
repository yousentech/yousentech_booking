from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

class BookingEventServiceLine(models.Model):
    _name="yousentech.booking.event.service.line"
    _description="Event Booking Service Line"
    booking_id=fields.Many2one("yousentech.booking.event",required=True,ondelete="cascade",index=True)
    company_id=fields.Many2one(related="booking_id.company_id",store=True,index=True)
    service_id=fields.Many2one("yousentech.booking.service",required=True,domain="[('company_id','=',company_id)]")
    quantity=fields.Float(default=1.0,required=True)
    price_unit=fields.Monetary(required=True)
    subtotal=fields.Monetary(compute="_compute_subtotal",store=True)
    currency_id=fields.Many2one(related="booking_id.currency_id",store=True,readonly=True)
    @api.depends("quantity","price_unit")
    def _compute_subtotal(self):
        for line in self: line.subtotal=line.quantity*line.price_unit

class BookingEvent(models.Model):
    _inherit="yousentech.booking.event"
    package_id=fields.Many2one("yousentech.booking.package",domain="[('company_id','=',company_id)]")
    service_line_ids=fields.One2many("yousentech.booking.event.service.line","booking_id")
    discount_type=fields.Selection([("none","No Discount"),("percent","Percentage"),("fixed","Fixed")],default="none",required=True)
    discount_value=fields.Float(default=0.0)
    amount_untaxed=fields.Monetary(compute="_compute_amounts",store=True)
    discount_amount=fields.Monetary(compute="_compute_amounts",store=True)
    amount_total=fields.Monetary(compute="_compute_amounts",store=True,tracking=True)

    @api.onchange("package_id")
    def _onchange_package_id(self):
        if not self.package_id: return
        self.service_line_ids=[fields.Command.clear()]+[fields.Command.create({"service_id":l.service_id.id,"quantity":l.quantity,"price_unit":l.price_unit}) for l in self.package_id.line_ids]

    @api.depends("hall_id.list_price","package_id.price","service_line_ids.subtotal","discount_type","discount_value")
    def _compute_amounts(self):
        for rec in self:
            services=sum(rec.service_line_ids.mapped("subtotal"))
            base=(rec.hall_id.list_price or 0.0)+services
            if rec.package_id and rec.package_id.pricing_type=="fixed":
                base=(rec.hall_id.list_price or 0.0)+(rec.package_id.price or 0.0)
            discount=base*min(max(rec.discount_value,0.0),100.0)/100.0 if rec.discount_type=="percent" else min(max(rec.discount_value,0.0),base) if rec.discount_type=="fixed" else 0.0
            rec.amount_untaxed=base; rec.discount_amount=discount; rec.amount_total=base-discount

    @api.constrains("discount_type","discount_value")
    def _check_discount(self):
        for rec in self:
            if rec.discount_value<0 or (rec.discount_type=="percent" and rec.discount_value>100): raise ValidationError(_("Invalid discount value."))

    def write(self,vals):
        if {"discount_type","discount_value"} & set(vals) and not self.env.user.has_group("yousentech_booking.group_booking_supervisor"):
            for rec in self:
                new_type=vals.get("discount_type",rec.discount_type); new_value=vals.get("discount_value",rec.discount_value)
                if new_type!="none" and new_value: raise AccessError(_("Only a booking supervisor or manager can apply discounts."))
        return super().write(vals)

    @api.model_create_multi
    def create(self,vals_list):
        if not self.env.user.has_group("yousentech_booking.group_booking_supervisor"):
            for vals in vals_list:
                if vals.get("discount_type","none")!="none" and vals.get("discount_value",0): raise AccessError(_("Only a booking supervisor or manager can apply discounts."))
        return super().create(vals_list)
