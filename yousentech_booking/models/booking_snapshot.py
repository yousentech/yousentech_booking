import json
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class BookingCommercialSnapshot(models.Model):
    _name="yousentech.booking.commercial.snapshot"
    _description="Booking Commercial Snapshot"
    _order="revision desc, id desc"

    company_id=fields.Many2one("res.company",required=True,index=True)
    event_booking_id=fields.Many2one("yousentech.booking.event",ondelete="restrict",index=True)
    stay_booking_id=fields.Many2one("yousentech.stay.booking",ondelete="restrict",index=True)
    revision=fields.Integer(required=True,default=1,readonly=True)
    currency_id=fields.Many2one("res.currency",required=True,readonly=True)
    amount_total=fields.Monetary(readonly=True)
    payload=fields.Text(required=True,readonly=True)
    locked=fields.Boolean(default=True,readonly=True)

    @api.constrains("event_booking_id","stay_booking_id")
    def _check_booking_link(self):
        for rec in self:
            if bool(rec.event_booking_id)==bool(rec.stay_booking_id):
                raise ValidationError(_("A commercial snapshot must belong to exactly one booking."))

    def write(self,vals):
        if self.filtered("locked") and not self.env.context.get("booking_snapshot_system_write"):
            raise UserError(_("Confirmed commercial snapshots are immutable."))
        return super().write(vals)

    def unlink(self):
        if self.filtered("locked"):
            raise UserError(_("Confirmed commercial snapshots cannot be deleted."))
        return super().unlink()

    @classmethod
    def _json(cls,payload):
        return json.dumps(payload,ensure_ascii=False,sort_keys=True,default=str)

    @api.model
    def _next_revision(self,field_name,booking_id):
        latest=self.search([(field_name,"=",booking_id)],order="revision desc,id desc",limit=1)
        return (latest.revision or 0)+1

class BookingEvent(models.Model):
    _inherit="yousentech.booking.event"
    commercial_snapshot_ids=fields.One2many("yousentech.booking.commercial.snapshot","event_booking_id",readonly=True)

    def _create_commercial_snapshot(self):
        Snapshot=self.env["yousentech.booking.commercial.snapshot"].sudo()
        for rec in self:
            payload={"kind":"event","booking":rec.name,"hall":{"id":rec.hall_id.id,"name":rec.hall_id.display_name,"price":rec.hall_id.list_price},"period_ids":rec.period_ids.ids,"package":{"id":rec.package_id.id,"name":rec.package_id.display_name,"price":rec.package_id.price} if rec.package_id else None,"services":[{"service_id":l.service_id.id,"name":l.service_id.display_name,"qty":l.quantity,"price_unit":l.price_unit,"subtotal":l.subtotal} for l in rec.service_line_ids],"discount_type":rec.discount_type,"discount_value":rec.discount_value,"discount_amount":rec.discount_amount,"amount_total":rec.amount_total}
            Snapshot.create({"company_id":rec.company_id.id,"event_booking_id":rec.id,"revision":Snapshot._next_revision("event_booking_id",rec.id),"currency_id":rec.currency_id.id,"amount_total":rec.amount_total,"payload":Snapshot._json(payload)})

class StayBooking(models.Model):
    _inherit="yousentech.stay.booking"
    commercial_snapshot_ids=fields.One2many("yousentech.booking.commercial.snapshot","stay_booking_id",readonly=True)

    def _create_commercial_snapshot(self):
        Snapshot=self.env["yousentech.booking.commercial.snapshot"].sudo()
        for rec in self:
            payload={"kind":"stay","booking":rec.name,"resource":{"id":rec.resource_id.id,"name":rec.resource_id.display_name},"rate_plan":{"id":rec.rate_plan_id.id,"name":rec.rate_plan_id.display_name} if rec.rate_plan_id else None,"nights":rec.nights,"nightly_price":rec.nightly_price,"addons":[{"addon_id":l.addon_id.id,"name":l.addon_id.display_name,"charge_type":l.addon_id.charge_type,"qty":l.quantity,"price_unit":l.price_unit,"subtotal":l.subtotal} for l in rec.addon_line_ids],"amount_total":rec.amount_total}
            Snapshot.create({"company_id":rec.company_id.id,"stay_booking_id":rec.id,"revision":Snapshot._next_revision("stay_booking_id",rec.id),"currency_id":rec.currency_id.id,"amount_total":rec.amount_total,"payload":Snapshot._json(payload)})
