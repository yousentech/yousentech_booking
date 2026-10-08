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

class BookingEventAddonLine(models.Model):
    _name = "yousentech.booking.event.addon.line"
    _inherit = "yousentech.booking.event.service.line"
    _description = "Paid Event Booking Add-on"

class BookingEvent(models.Model):
    _inherit="yousentech.booking.event"
    package_id=fields.Many2one("yousentech.booking.package",domain="[('company_id','=',company_id)]")
    service_line_ids=fields.One2many("yousentech.booking.event.service.line","booking_id")
    addon_line_ids=fields.One2many("yousentech.booking.event.addon.line","booking_id",string="الخدمات الملحقة المدفوعة")
    hall_period_amount=fields.Monetary(compute="_compute_amounts",string="إجمالي فترات القاعة")
    booking_tax_id=fields.Many2one("account.tax",compute="_compute_booking_tax",string="نوع الضريبة",readonly=True)
    period_price_details=fields.Text(compute="_compute_period_price_details",string="تفصيل أسعار الفترات",readonly=True)
    discount_type=fields.Selection([("none","No Discount"),("percent","Percentage"),("fixed","Fixed")],default="none",required=True)
    discount_value=fields.Float(default=0.0)
    amount_untaxed=fields.Monetary(compute="_compute_amounts",store=True)
    discount_amount=fields.Monetary(compute="_compute_amounts",store=True)
    tax_amount=fields.Monetary(compute="_compute_amounts",store=True)
    amount_total=fields.Monetary(compute="_compute_amounts",store=True,tracking=True)

    @api.depends("package_id", "package_id.tax_id", "hall_id", "hall_id.tax_id")
    def _compute_booking_tax(self):
        for rec in self:
            rec.booking_tax_id = rec.package_id.tax_id if rec.package_id else rec.hall_id.tax_id

    def _get_hall_period_prices(self):
        """Use configured period prices; never silently substitute the default
        when the hall has a per-period price table."""
        self.ensure_one()
        if not self.hall_id or not self.period_ids:
            return []
        lines = self.hall_id.period_price_ids
        configured = {line.period_id.id: line.price for line in lines}
        missing = self.period_ids.filtered(lambda period: period.id not in configured)
        if lines and missing:
            raise ValidationError(
                _("No configured hall price for period(s): %s. Configure all selected periods on the hall before saving the booking.")
                % ", ".join(missing.mapped("display_name"))
            )
        return [(period, configured[period.id] if lines else self.hall_id.list_price or 0.0)
                for period in self.period_ids]

    @api.constrains("hall_id", "period_ids", "company_id")
    def _check_hall_period_pricing(self):
        for booking in self:
            booking._get_hall_period_prices()

    @api.depends("hall_id", "hall_id.list_price", "hall_id.period_price_ids",
                 "hall_id.period_price_ids.price", "hall_id.period_price_ids.period_id", "period_ids")
    def _compute_period_price_details(self):
        for rec in self:
            rec.period_price_details = " | ".join(
                "%s: %.2f" % (period.display_name, price)
                for period, price in rec._get_hall_period_prices()
            )

    @staticmethod
    def _package_commands(package):
        return [fields.Command.create({"service_id":line.service_id.id,"quantity":line.quantity,"price_unit":line.price_unit}) for line in package.line_ids]

    @api.onchange("package_id")
    def _onchange_package_id(self):
        # Clear old included lines even when the package is removed.
        self.service_line_ids = [fields.Command.clear()] + (self._package_commands(self.package_id) if self.package_id else [])

    @api.depends("hall_id","hall_id.list_price","hall_id.tax_id","hall_id.period_price_ids","hall_id.period_price_ids.price","hall_id.period_price_ids.period_id","period_ids","package_id.price","package_id.pricing_type",
                 "package_id.tax_id","service_line_ids.subtotal","addon_line_ids.subtotal",
                 "discount_type","discount_value","partner_id")
    def _compute_amounts(self):
        for rec in self:
            fixed = bool(rec.package_id and rec.package_id.pricing_type == "fixed")
            package_price = rec.package_id.price if rec.package_id else 0.0
            package_base = package_price if fixed else sum(rec.service_line_ids.mapped("subtotal"))
            period_prices = rec._get_hall_period_prices()
            hall_period_price = sum(price for _period, price in period_prices)
            rec.hall_period_amount = hall_period_price
            # Included services never become paid add-ons.
            # A selected package replaces the hall base rate; never charge both.
            gross = (package_base * len(rec.period_ids)) if rec.package_id else hall_period_price
            gross += sum(rec.addon_line_ids.mapped("subtotal"))
            # All prices are converted to tax-excluded values before applying booking discount.
            tax = rec.package_id.tax_id if rec.package_id else rec.hall_id.tax_id
            def split(price, qty=1.0, product=False):
                if not tax:
                    return price * qty
                return tax.compute_all(price, currency=rec.currency_id, quantity=qty,
                                       product=product, partner=rec.partner_id)["total_excluded"]
            untaxed_gross = (split(package_price, len(rec.period_ids)) if fixed else
                             sum(split(l.price_unit, l.quantity * len(rec.period_ids), l.service_id.product_id) for l in rec.service_line_ids)
                             if rec.package_id else sum(split(price) for _period, price in period_prices))
            untaxed_gross += sum(split(l.price_unit, l.quantity, l.service_id.product_id) for l in rec.addon_line_ids)
            discount = (untaxed_gross * rec.discount_value / 100.0 if rec.discount_type == "percent"
                        else min(rec.discount_value, untaxed_gross) if rec.discount_type == "fixed" else 0.0)
            discount = max(0.0, discount)
            factor = (untaxed_gross - discount) / untaxed_gross if untaxed_gross else 1.0
            def taxed_amount(price, qty=1.0, product=False):
                if not tax:
                    return 0.0
                # Price-included taxes require recomputing a tax-inclusive discounted unit price.
                unit = price * factor
                result = tax.compute_all(unit, currency=rec.currency_id, quantity=qty,
                                         product=product, partner=rec.partner_id)
                return result["total_included"] - result["total_excluded"]
            tax_total = (taxed_amount(package_price, len(rec.period_ids)) if fixed else
                         sum(taxed_amount(l.price_unit, l.quantity * len(rec.period_ids), l.service_id.product_id) for l in rec.service_line_ids)
                         if rec.package_id else sum(taxed_amount(price) for _period, price in period_prices))
            tax_total += sum(taxed_amount(l.price_unit, l.quantity, l.service_id.product_id) for l in rec.addon_line_ids)
            rec.amount_untaxed = untaxed_gross - discount
            rec.discount_amount = discount
            rec.tax_amount = tax_total
            rec.amount_total = rec.amount_untaxed + tax_total

    @api.constrains("discount_type","discount_value","package_id")
    def _check_commercial(self):
        for rec in self:
            if rec.discount_value<0 or (rec.discount_type=="percent" and rec.discount_value>100):
                raise ValidationError(_("Invalid discount value."))
            if rec.package_id and rec.package_id.company_id!=rec.company_id:
                raise ValidationError(_("Package must belong to the booking branch/company."))

    def write(self,vals):
        commercial={"package_id","service_line_ids","addon_line_ids","discount_type","discount_value","hall_id"}
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
