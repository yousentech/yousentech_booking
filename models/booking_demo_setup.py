from odoo import _, fields, models
from odoo.exceptions import UserError


class BookingDemoSetup(models.TransientModel):
    _name = "yousentech.booking.demo.setup"
    _description = "Booking Demo Setup"

    company_id = fields.Many2one(
        "res.company",
        string="Branch / Company",
        required=True,
        default=lambda self: self.env.company,
    )

    def _get_or_create(self, model_name, domain, values):
        record = self.env[model_name].with_company(self.company_id).search(domain, limit=1)
        if record:
            return record
        return self.env[model_name].with_company(self.company_id).create(values)

    def _demo_product(self, name, list_price):
        Product = self.env["product.product"].with_company(self.company_id)
        product = Product.search([
            ("name", "=", name),
            "|",
            ("company_id", "=", False),
            ("company_id", "=", self.company_id.id),
        ], limit=1)
        if product:
            return product
        return Product.create({
            "name": name,
            "sale_ok": True,
            "purchase_ok": False,
            "type": "service",
            "list_price": list_price,
            "company_id": self.company_id.id,
        })

    def action_seed_demo(self):
        self.ensure_one()
        if not self.env.user.has_group("yousentech_booking.group_booking_manager"):
            raise UserError(_("Only Booking Managers can initialize demo configuration."))

        company = self.company_id
        common = {"company_id": company.id, "active": True}
        is_arabic = (self.env.user.lang or "").lower().startswith("ar")

        def tr(arabic, english):
            return arabic if is_arabic else english

        periods = [
            (tr("صباحي", "Morning"), 10),
            (tr("مسائي", "Evening"), 20),
        ]
        for name, sequence in periods:
            self._get_or_create(
                "yousentech.booking.period",
                [("company_id", "=", company.id), ("name", "=", name)],
                {**common, "name": name, "sequence": sequence},
            )

        halls = [
            (tr("القاعة الرئيسية", "Main Hall"), 300, 5000.0, 10),
            (tr("قاعة العائلات", "Family Hall"), 150, 3000.0, 20),
            (tr("قاعة الاجتماعات", "Meeting Hall"), 50, 1500.0, 30),
        ]
        for name, capacity, price, sequence in halls:
            self._get_or_create(
                "yousentech.booking.hall",
                [("company_id", "=", company.id), ("name", "=", name)],
                {**common, "name": name, "capacity": capacity, "list_price": price, "sequence": sequence},
            )

        service_specs = [
            (tr("الضيافة", "Hospitality"), 750.0, 10),
            (tr("الديكور", "Decoration"), 1200.0, 20),
            (tr("النظام الصوتي", "Sound System"), 500.0, 30),
        ]
        services = {}
        for name, price, sequence in service_specs:
            product = self._demo_product("%s - %s" % (tr("حجوزات", "Booking"), name), price)
            services[name] = self._get_or_create(
                "yousentech.booking.service",
                [("company_id", "=", company.id), ("name", "=", name)],
                {**common, "name": name, "sequence": sequence, "product_id": product.id, "price": price},
            )

        package_name = tr("باقة المناسبات القياسية", "Standard Event Package")
        package = self._get_or_create(
            "yousentech.booking.package",
            [("company_id", "=", company.id), ("name", "=", package_name)],
            {**common, "name": package_name, "sequence": 10, "pricing_type": "fixed", "fixed_price": 2000.0},
        )
        for sequence, service_name in enumerate(services, start=1):
            service = services[service_name]
            self._get_or_create(
                "yousentech.booking.package.line",
                [("package_id", "=", package.id), ("service_id", "=", service.id)],
                {"package_id": package.id, "service_id": service.id, "quantity": 1.0, "sequence": sequence * 10},
            )

        resources = [
            (tr("غرفة 101", "Room 101"), "room", 2, 350.0, 10),
            (tr("غرفة 102", "Room 102"), "room", 2, 350.0, 20),
            (tr("جناح 201", "Suite 201"), "suite", 4, 650.0, 30),
            (tr("شاليه 1", "Chalet 1"), "chalet", 6, 900.0, 40),
        ]
        for name, resource_type, capacity, price, sequence in resources:
            self._get_or_create(
                "yousentech.stay.resource",
                [("company_id", "=", company.id), ("name", "=", name)],
                {**common, "name": name, "resource_type": resource_type, "capacity": capacity, "nightly_price": price, "sequence": sequence},
            )

        rate_plans = [
            (tr("السعر القياسي", "Standard Rate"), "resource", 0.0, 0.0, 10),
            (tr("نهاية الأسبوع +10%", "Weekend +10%"), "percent", 0.0, 10.0, 20),
            (tr("سعر ديمو ثابت", "Demo Fixed Rate"), "fixed", 400.0, 0.0, 30),
        ]
        for name, pricing_type, fixed_price, adjustment, sequence in rate_plans:
            self._get_or_create(
                "yousentech.stay.rate.plan",
                [("company_id", "=", company.id), ("name", "=", name)],
                {**common, "name": name, "pricing_type": pricing_type, "fixed_price": fixed_price,
                 "percent_adjustment": adjustment, "sequence": sequence},
            )

        addon_specs = [
            (tr("سرير إضافي", "Extra Bed"), 100.0, "night", 10),
            (tr("الإفطار", "Breakfast"), 50.0, "night", 20),
            (tr("توصيل المطار", "Airport Transfer"), 150.0, "once", 30),
        ]
        for name, price, charge_type, sequence in addon_specs:
            product = self._demo_product("%s - %s" % (tr("إقامة", "Stay"), name), price)
            self._get_or_create(
                "yousentech.stay.addon",
                [("company_id", "=", company.id), ("name", "=", name)],
                {**common, "name": name, "product_id": product.id, "price": price,
                 "charge_type": charge_type, "sequence": sequence},
            )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Demo configuration ready"),
                "message": _("Demo booking configuration was initialized for %s without duplicating existing demo records.") % company.display_name,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
