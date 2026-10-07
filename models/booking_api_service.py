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
            checkout=fields.Date.to_date(checkout_date) if checkout_date else False
        except Exception:
            return self._error("INVALID_PAYLOAD","Invalid stay dates.")
        if not checkin:
            return self._error("INVALID_PAYLOAD","تاريخ الدخول غير صالح.")
        if not checkout and not company.booking_allow_open_stay:
            return self._error("INVALID_PAYLOAD","تاريخ الخروج إجباري حسب إعدادات الشركة / الفرع.")
        if checkout and checkout<=checkin:
            return self._error("INVALID_PAYLOAD","تاريخ الخروج يجب أن يكون بعد تاريخ الدخول.")
        resources=self.env["yousentech.stay.resource"].with_company(company).search([("company_id","=",company.id),("active","=",True)])
        domain=[("company_id","=",company.id),("state","in",["hold","confirmed","checked_in","checked_out"]),"|",("checkout_date","=",False),("checkout_date",">",checkin)]
        if checkout:
            domain.append(("checkin_date","<",checkout))
        blocked=self.env["yousentech.stay.booking"].with_company(company).search(domain)
        blocked_ids=set(blocked.mapped("resource_id").ids)
        return self._ok({"resources":[{"id":r.id,"name":r.name,"resource_type":r.resource_type,"capacity":r.capacity,"available":r.id not in blocked_ids} for r in resources]})

    @api.model
    def create_event(self,payload):
        company=self._company(payload.get("company_id"))
        if not company:
            return self._error("COMPANY_NOT_ALLOWED","Branch/company is not allowed.")
        try:
            if payload.get("package_id") and payload.get("service_lines"):
                return self._error("INVALID_PAYLOAD","Use either a package or explicit service lines, not both.")
            vals={"company_id":company.id,"partner_id":int(payload["partner_id"]),"booking_date":payload["booking_date"],"hall_id":int(payload["hall_id"]),"period_ids":[fields.Command.set([int(x) for x in payload.get("period_ids",[])])],"invoice_policy":payload.get("invoice_policy","manual")}
            if payload.get("package_id"): vals["package_id"]=int(payload["package_id"])
            if payload.get("service_lines"): vals["service_line_ids"]=[fields.Command.create({"service_id":int(line["service_id"]),"quantity":float(line.get("quantity",1))}) for line in payload["service_lines"]]
            if payload.get("discount_type"): vals["discount_type"]=payload["discount_type"]
            if "discount_value" in payload: vals["discount_value"]=float(payload["discount_value"])
            if "deposit_percent" in payload: vals["deposit_percent"]=float(payload["deposit_percent"])
            rec=self.env["yousentech.booking.event"].with_company(company).create(vals)
            return self._ok(self.serialize_booking(rec))
        except (KeyError,ValueError,TypeError):
            return self._error("INVALID_PAYLOAD","Required event booking data is invalid.")
        except AccessError as exc:
            return self._error("DISCOUNT_NOT_ALLOWED" if "discount" in str(exc).lower() else "ACCESS_DENIED",str(exc))
        except (UserError,ValidationError) as exc:
            return self._error("PERIOD_ALREADY_BOOKED" if "already booked" in str(exc).lower() else "INVALID_STATE",str(exc))

    @api.model
    def create_stay(self,payload):
        company=self._company(payload.get("company_id"))
        if not company:
            return self._error("COMPANY_NOT_ALLOWED","Branch/company is not allowed.")
        try:
            vals={"company_id":company.id,"partner_id":int(payload["partner_id"]),"resource_id":int(payload["resource_id"]),"checkin_date":payload["checkin_date"],"checkout_date":payload.get("checkout_date") or False,"invoice_policy":payload.get("invoice_policy","manual")}
            if payload.get("rate_plan_id"): vals["rate_plan_id"]=int(payload["rate_plan_id"])
            if payload.get("addon_lines"): vals["addon_line_ids"]=[fields.Command.create({"addon_id":int(line["addon_id"]),"quantity":float(line.get("quantity",1))}) for line in payload["addon_lines"]]
            if "deposit_percent" in payload: vals["deposit_percent"]=float(payload["deposit_percent"])
            rec=self.env["yousentech.stay.booking"].with_company(company).create(vals)
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
            data.update({"kind":"stay","checkin_date":fields.Date.to_string(rec.checkin_date),"checkout_date":fields.Date.to_string(rec.checkout_date) if rec.checkout_date else False,"resource_id":rec.resource_id.id,"nights":rec.nights})
        return data

    @api.model
    def get_booking(self,kind,record_id):
        model="yousentech.booking.event" if kind=="event" else "yousentech.stay.booking" if kind=="stay" else False
        if not model:
            return self._error("INVALID_PAYLOAD","Unknown booking kind.")
        rec=self.env[model].browse(int(record_id)).exists()
        if not rec:
            return self._error("NOT_FOUND","Booking was not found.")
        return self._ok(self.serialize_booking(rec))

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
            low=msg.lower()
            if "already booked" in low: code="PERIOD_ALREADY_BOOKED"
            elif "not available" in low or "conflict" in low: code="RESOURCE_NOT_AVAILABLE"
            elif "invoice" in low or "accounting" in low: code="PAYMENT_REQUIRED"
            else: code="INVALID_STATE"
            return self._error(code,msg)
