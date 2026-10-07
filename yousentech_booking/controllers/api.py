from odoo import http
from odoo.http import request

class BookingApi(http.Controller):
    def _ok(self, data): return {"success":True,"api_version":"2.0","data":data}
    def _error(self, code, message): return {"success":False,"api_version":"2.0","error":{"code":code,"message":message}}

    @http.route("/api/v2/booking/bootstrap", type="json", auth="user", methods=["POST"], csrf=False)
    def bootstrap(self, **payload):
        companies=request.env.companies
        return self._ok({"current_company_id":request.env.company.id,"companies":[{"id":c.id,"name":c.name,"currency":c.currency_id.name} for c in companies]})

    @http.route("/api/v2/events/availability", type="json", auth="user", methods=["POST"], csrf=False)
    def event_availability(self, company_id=None, booking_date=None, **payload):
        if not company_id or not booking_date: return self._error("INVALID_PAYLOAD","company_id and booking_date are required.")
        return request.env["yousentech.booking.api.service"].event_availability(int(company_id), booking_date)
