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

        periods = [
            ("Morning", 10),
            ("Evening", 20),
        ]
        for name, sequence in periods:
            self._get_or_create(
                "yousentech.booking.period",
                [("company_id", "=", company.id), ("name", "=", name)],
                {**common, "name": name, "sequence": sequence},
            )

        halls = [
            ("Main Hall", 300, 5000.0, 10),
            ("Family Hall", 150, 3000.0, 20),
            ("Meeting Hall", 50, 1500.0, 30),
        ]
        for name, capacity, price, sequence in halls:
            self._get_or_create(
                "yousentech.booking.hall",
                [("company_id", "=", company.id), ("name", "=", name)],
                {**common, "name": name, "capacity": capacity, "list_price": price, "sequence": sequence},
            )

        service_specs = [
            ("Hospitality", 750.0, 10),
            ("Decoration", 1200.0, 20),
            ("Sound System", 500.0, 30),
        ]
        services = {}
        for name, price, sequence in service_specs:
            product = self._demo_product("Booking - %s" % name, price)
            services[name] = self._get_or_create(
                "yousentech.booking.service",
                [("company_id", "=", company.id), ("name", "=", name)],
                {**common, "name": name, "sequence": sequence, "product_id": product.id, "price": price},
            )

        package = self._get_or_create(
            "yousentech.booking.package",
            [("company_id", "=", company.id), ("name", "=", "Standard Event Package")],
            {**common, "name": "Standard Event Package", "sequence": 10, "pricing_type": "fixed", "fixed_price": 2000.0},
        )
        for sequence, service_name in enumerate(("Hospitality", "Decoration", "Sound System"), start=1):
            service = services[service_name]
            self._get_or_create(
                "yousentech.booking.package.line",
                [("package_id", "=", package.id), ("service_id", "=", service.id)],
                {"package_id": package.id, "service_id": service.id, "quantity": 1.0, "sequence": sequence * 10},
            )

        resources = [
            ("Room 101", "room", 2, 350.0, 10),
            ("Room 102", "room", 2, 350.0, 20),
            ("Suite 201", "suite", 4, 650.0, 30),
            ("Chalet 1", "chalet", 6, 900.0, 40),
        ]
        for name, resource_type, capacity, price, sequence in resources:
            self._get_or_create(
                "yousentech.stay.resource",
                [("company_id", "=", company.id), ("name", "=", name)],
                {**common, "name": name, "resource_type": resource_type, "capacity": capacity, "nightly_price": price, "sequence": sequence},
            )

        rate_plans = [
            ("Standard Rate", "resource", 0.0, 0.0, 10),
            ("Weekend +10%", "percent", 0.0, 10.0, 20),
            ("Demo Fixed Rate", "fixed", 400.0, 0.0, 30),
        ]
        for name, pricing_type, fixed_price, adjustment, sequence in rate_plans:
            self._get_or_create(
                "yousentech.stay.rate.plan",
                [("company_id", "=", company.id), ("name", "=", name)],
                {**common, "name": name, "pricing_type": pricing_type, "fixed_price": fixed_price,
                 "percent_adjustment": adjustment, "sequence": sequence},
            )

        addon_specs = [
            ("Extra Bed", 100.0, "night", 10),
            ("Breakfast", 50.0, "night", 20),
            ("Airport Transfer", 150.0, "once", 30),
        ]
        for name, price, charge_type, sequence in addon_specs:
            product = self._demo_product("Stay - %s" % name, price)
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
