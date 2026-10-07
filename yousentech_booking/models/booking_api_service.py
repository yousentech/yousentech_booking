from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

class BookingApiService(models.AbstractModel):
    _name="yousentech.booking.api.service"
    _description="Booking API Service"

    def _error(self,code,message):
        return {"success":False,"api_version":"2.0","error":{"code":code,"message":message}}

    def _ok(self,data):
        return {"success":True,"api_version":"2.0","data":data}

    def _company(self,company_id):
        company=self.env["res.company"].browse(int(company_id)).exists()
        return company if company and company in self.env.companies else False

    @api.model
    def event_availability(self,company_id,booking_date):
        company=self._company(company_id)
        if not company:
            return self._error("COMPANY_NOT_ALLOWED","Branch/company is not allowed.")
        try:
            booking_date=fields.Date.to_date(booking_date)
        except Exception:
            return self._error("INVALID_PAYLOAD","Invalid booking date.")
        halls=self.env["yousentech.booking.hall"].with_company(company).search([("company_id","=",company.id),("active","=",True)])
        periods=self.env["yousentech.booking.period"].with_company(company).search([("company_id","=",company.id),("active","=",True)])
        blocked=self.env["yousentech.booking.event"].with_company(company).search([("company_id","=",company.id),("booking_date","=",booking_date),("state","in",["hold","confirmed","preparing","event","completed"])])
        used={(b.hall_id.id,p.id):b.id for b in blocked for p in b.period_ids}
        return self._ok({"halls":[{"id":h.id,"name":h.name,"periods":[{"id":p.id,"name":p.name,"available":(h.id,p.id) not in used} for p in periods]} for h in halls]})

    @api.model
    def stay_availability(self,company_id,checkin_date,checkout_date):
        company=self._company(company_id)
        if not company:
            return self._error("COMPANY_NOT_ALLOWED","Branch/company is not allowed.")
        try:
            checkin=fields.Date.to_date(checkin_date)
            checkout=fields.Date.to_date(checkout_date)
        except Exception:
            return self._error("INVALID_PAYLOAD","Invalid stay dates.")
        if not checkin or not checkout or checkout<=checkin:
            return self._error("INVALID_PAYLOAD","Checkout must be after check-in.")
        resources=self.env["yousentech.stay.resource"].with_company(company).search([("company_id","=",company.id),("active","=",True)])
        blocked=self.env["yousentech.stay.booking"].with_company(company).search([("company_id","=",company.id),("state","in",["hold","confirmed","checked_in","checked_out"]),("checkin_date","<",checkout),("checkout_date",">",checkin)])
        blocked_ids=set(blocked.mapped("resource_id").ids)
        return self._ok({"resources":[{"id":r.id,"name":r.name,"resource_type":r.resource_type,"capacity":r.capacity,"available":r.id not in blocked_ids} for r in resources]})

    @api.model
    def create_event(self,payload):
        company=self._company(payload.get("company_id"))
        if not company:
            return self._error("COMPANY_NOT_ALLOWED","Branch/company is not allowed.")
        try:
            rec=self.env["yousentech.booking.event"].with_company(company).create({
                "company_id":company.id,
                "partner_id":int(payload["partner_id"]),
                "booking_date":payload["booking_date"],
                "hall_id":int(payload["hall_id"]),
                "period_ids":[fields.Command.set([int(x) for x in payload.get("period_ids",[])])],
                "invoice_policy":payload.get("invoice_policy","manual"),
            })
            return self._ok(self.serialize_booking(rec))
        except (KeyError,ValueError,TypeError):
            return self._error("INVALID_PAYLOAD","Required event booking data is invalid.")
        except (AccessError,UserError,ValidationError) as exc:
            return self._error("PERIOD_ALREADY_BOOKED" if "already booked" in str(exc).lower() else "INVALID_STATE",str(exc))

    @api.model
    def create_stay(self,payload):
        company=self._company(payload.get("company_id"))
        if not company:
            return self._error("COMPANY_NOT_ALLOWED","Branch/company is not allowed.")
        try:
            rec=self.env["yousentech.stay.booking"].with_company(company).create({
                "company_id":company.id,
                "partner_id":int(payload["partner_id"]),
                "resource_id":int(payload["resource_id"]),
                "checkin_date":payload["checkin_date"],
                "checkout_date":payload["checkout_date"],
                "invoice_policy":payload.get("invoice_policy","manual"),
            })
            return self._ok(self.serialize_booking(rec))
        except (KeyError,ValueError,TypeError):
            return self._error("INVALID_PAYLOAD","Required stay booking data is invalid.")
        except (AccessError,UserError,ValidationError) as exc:
            return self._error("RESOURCE_NOT_AVAILABLE" if "not available" in str(exc).lower() else "INVALID_STATE",str(exc))

    @api.model
    def serialize_booking(self,rec):
        rec.ensure_one()
        data={"id":rec.id,"name":rec.name,"company_id":rec.company_id.id,"partner_id":rec.partner_id.id,"state":rec.state,"amount_total":rec.amount_total,"currency":rec.currency_id.name,"finance_state":rec.finance_state,"amount_invoiced":rec.amount_invoiced,"amount_paid":rec.amount_paid,"amount_due":rec.amount_due,"amount_to_invoice":rec.amount_to_invoice,"allowed_actions":rec._allowed_actions()}
        if rec._name=="yousentech.booking.event":
            data.update({"kind":"event","booking_date":fields.Date.to_string(rec.booking_date),"hall_id":rec.hall_id.id,"period_ids":rec.period_ids.ids})
        else:
            data.update({"kind":"stay","checkin_date":fields.Date.to_string(rec.checkin_date),"checkout_date":fields.Date.to_string(rec.checkout_date),"resource_id":rec.resource_id.id,"nights":rec.nights})
        return data

    @api.model
    def transition(self,kind,record_id,action,reason=None):
        model="yousentech.booking.event" if kind=="event" else "yousentech.stay.booking" if kind=="stay" else False
        if not model:
            return self._error("INVALID_PAYLOAD","Unknown booking kind.")
        rec=self.env[model].browse(int(record_id)).exists()
        if not rec:
            return self._error("NOT_FOUND","Booking was not found.")
        methods={"hold":"action_hold","confirmed":"action_confirm","preparing":"action_prepare","event":"action_start_event","completed":"action_complete","checked_in":"action_check_in","checked_out":"action_check_out","cancelled":"action_cancel","draft":"action_reopen"}
        method=methods.get(action)
        if not method or not hasattr(rec,method):
            return self._error("INVALID_STATE","Action is not supported for this booking.")
        try:
            getattr(rec,method)(reason) if action=="cancelled" else getattr(rec,method)()
            return self._ok(self.serialize_booking(rec))
        except AccessError as exc:
            return self._error("ACCESS_DENIED",str(exc))
        except (UserError,ValidationError) as exc:
            msg=str(exc)
            code="PAYMENT_REQUIRED" if "invoice" in msg.lower() or "accounting" in msg.lower() else "INVALID_STATE"
            return self._error(code,msg)
