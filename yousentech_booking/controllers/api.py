from odoo import http
from odoo.http import request

class BookingApi(http.Controller):
    def _ok(self,data):
        return {"success":True,"api_version":"2.0","data":data}
    def _error(self,code,message):
        return {"success":False,"api_version":"2.0","error":{"code":code,"message":message}}

    @http.route("/api/v2/booking/bootstrap",type="json",auth="user",methods=["POST"],csrf=False)
    def bootstrap(self,**payload):
        companies=request.env.companies
        return self._ok({"current_company_id":request.env.company.id,"companies":[{"id":c.id,"name":c.name,"currency":c.currency_id.name} for c in companies]})

    @http.route("/api/v2/events/availability",type="json",auth="user",methods=["POST"],csrf=False)
    def event_availability(self,company_id=None,booking_date=None,**payload):
        if not company_id or not booking_date:
            return self._error("INVALID_PAYLOAD","company_id and booking_date are required.")
        return request.env["yousentech.booking.api.service"].event_availability(company_id,booking_date)

    @http.route("/api/v2/stays/availability",type="json",auth="user",methods=["POST"],csrf=False)
    def stay_availability(self,company_id=None,checkin_date=None,checkout_date=None,**payload):
        if not company_id or not checkin_date or not checkout_date:
            return self._error("INVALID_PAYLOAD","company_id, checkin_date and checkout_date are required.")
        return request.env["yousentech.booking.api.service"].stay_availability(company_id,checkin_date,checkout_date)

    @http.route("/api/v2/events",type="json",auth="user",methods=["POST"],csrf=False)
    def create_event(self,**payload):
        return request.env["yousentech.booking.api.service"].create_event(payload)

    @http.route("/api/v2/stays",type="json",auth="user",methods=["POST"],csrf=False)
    def create_stay(self,**payload):
        return request.env["yousentech.booking.api.service"].create_stay(payload)

    @http.route("/api/v2/bookings/action",type="json",auth="user",methods=["POST"],csrf=False)
    def booking_action(self,kind=None,record_id=None,action=None,reason=None,**payload):
        if not kind or not record_id or not action:
            return self._error("INVALID_PAYLOAD","kind, record_id and action are required.")
        return request.env["yousentech.booking.api.service"].transition(kind,record_id,action,reason)
