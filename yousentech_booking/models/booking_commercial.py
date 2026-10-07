from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

LOCKED_STATES=("confirmed","preparing","event","completed")

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
        for line in self:
            line.subtotal=line.quantity*line.price_unit

    @api.constrains("service_id","quantity")
    def _check_values(self):
        for line in self:
            if line.quantity<=0:
                raise ValidationError(_("Service quantity must be greater than zero."))
            if line.service_id and line.booking_id and line.service_id.company_id!=line.booking_id.company_id:
                raise ValidationError(_("Service must belong to the booking branch/company."))

    @api.onchange("service_id")
    def _onchange_service_id(self):
        if self.service_id:
            self.price_unit=self.service_id.price

    @api.model_create_multi
    def create(self,vals_list):
        for vals in vals_list:
            booking=self.env["yousentech.booking.event"].browse(vals.get("booking_id")) if vals.get("booking_id") else False
            if booking and booking.state in LOCKED_STATES:
                raise ValidationError(_("Confirmed booking commercial lines cannot be changed."))
            service=self.env["yousentech.booking.service"].browse(vals.get("service_id")) if vals.get("service_id") else False
            if service and "price_unit" not in vals:
                vals["price_unit"]=service.price
        return super().create(vals_list)

    def write(self,vals):
        if self.filtered(lambda l:l.booking_id.state in LOCKED_STATES):
            raise ValidationError(_("Confirmed booking commercial lines cannot be changed."))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda l:l.booking_id.state in LOCKED_STATES):
            raise ValidationError(_("Confirmed booking commercial lines cannot be deleted."))
        return super().unlink()

class BookingEvent(models.Model):
    _inherit="yousentech.booking.event"
    package_id=fields.Many2one("yousentech.booking.package",domain="[('company_id','=',company_id)]")
    service_line_ids=fields.One2many("yousentech.booking.event.service.line","booking_id")
    discount_type=fields.Selection([("none","No Discount"),("percent","Percentage"),("fixed","Fixed")],default="none",required=True)
    discount_value=fields.Float(default=0.0)
    amount_untaxed=fields.Monetary(compute="_compute_amounts",store=True)
    discount_amount=fields.Monetary(compute="_compute_amounts",store=True)
    tax_amount=fields.Monetary(compute="_compute_amounts",store=True)
    amount_total=fields.Monetary(compute="_compute_amounts",store=True,tracking=True)

    @staticmethod
    def _package_commands(package):
        return [fields.Command.create({"service_id":line.service_id.id,"quantity":line.quantity,"price_unit":line.price_unit}) for line in package.line_ids]

    @api.onchange("package_id")
    def _onchange_package_id(self):
        if self.package_id:
            self.service_line_ids=[fields.Command.clear()]+self._package_commands(self.package_id)

    @api.depends("hall_id.list_price","package_id.price","package_id.pricing_type","service_line_ids.subtotal","service_line_ids.service_id.tax_ids","discount_type","discount_value","partner_id")
    def _compute_amounts(self):
        for rec in self:
            services=sum(rec.service_line_ids.mapped("subtotal"))
            base=(rec.hall_id.list_price or 0.0)+services
            fixed_package=rec.package_id and rec.package_id.pricing_type=="fixed"
            if fixed_package:
                base=(rec.hall_id.list_price or 0.0)+(rec.package_id.price or 0.0)
            discount=base*min(max(rec.discount_value,0.0),100.0)/100.0 if rec.discount_type=="percent" else min(max(rec.discount_value,0.0),base) if rec.discount_type=="fixed" else 0.0
            factor=(base-discount)/base if base else 1.0
            tax_amount=0.0
            if not fixed_package:
                for line in rec.service_line_ids:
                    taxes=line.service_id.tax_ids.compute_all(line.price_unit*factor,currency=rec.currency_id,quantity=line.quantity,product=line.service_id.product_id,partner=rec.partner_id)
                    tax_amount+=taxes["total_included"]-taxes["total_excluded"]
            rec.amount_untaxed=base-discount
            rec.discount_amount=discount
            rec.tax_amount=tax_amount
            rec.amount_total=rec.amount_untaxed+tax_amount

    @api.constrains("discount_type","discount_value","package_id")
    def _check_commercial(self):
        for rec in self:
            if rec.discount_value<0 or (rec.discount_type=="percent" and rec.discount_value>100):
                raise ValidationError(_("Invalid discount value."))
            if rec.package_id and rec.package_id.company_id!=rec.company_id:
                raise ValidationError(_("Package must belong to the booking branch/company."))

    def write(self,vals):
        commercial={"package_id","service_line_ids","discount_type","discount_value","hall_id"}
        if commercial & set(vals) and self.filtered(lambda r:r.state in LOCKED_STATES):
            raise ValidationError(_("Confirmed commercial terms are locked. Cancel and reopen the booking before changing them."))
        if {"discount_type","discount_value"} & set(vals) and not self.env.user.has_group("yousentech_booking.group_booking_manager"):
            for rec in self:
                new_type=vals.get("discount_type",rec.discount_type)
                new_value=vals.get("discount_value",rec.discount_value)
                if new_type!="none" and new_value:
                    raise AccessError(_("Only a booking manager can apply discounts."))
        if "package_id" in vals and "service_line_ids" not in vals:
            package=self.env["yousentech.booking.package"].browse(vals.get("package_id")) if vals.get("package_id") else False
            vals["service_line_ids"]=[fields.Command.clear()]+(self._package_commands(package) if package else [])
        return super().write(vals)

    @api.model_create_multi
    def create(self,vals_list):
        manager=self.env.user.has_group("yousentech_booking.group_booking_manager")
        for vals in vals_list:
            if not manager and vals.get("discount_type","none")!="none" and vals.get("discount_value",0):
                raise AccessError(_("Only a booking manager can apply discounts."))
            if vals.get("package_id") and "service_line_ids" not in vals:
                package=self.env["yousentech.booking.package"].browse(vals["package_id"])
                vals["service_line_ids"]=self._package_commands(package)
        return super().create(vals_list)
