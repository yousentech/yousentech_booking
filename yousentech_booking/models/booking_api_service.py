from odoo import api, models

class BookingApiService(models.AbstractModel):
    _name = "yousentech.booking.api.service"
    _description = "Booking API Service"

    @api.model
    def event_availability(self, company_id, booking_date):
        company = self.env["res.company"].browse(company_id).exists()
        if not company or company not in self.env.companies:
            return {"success": False, "error": {"code": "COMPANY_NOT_ALLOWED", "message": "Branch/company is not allowed."}}
        halls = self.env["yousentech.booking.hall"].with_company(company).search([("company_id","=",company.id),("active","=",True)])
        periods = self.env["yousentech.booking.period"].with_company(company).search([("company_id","=",company.id),("active","=",True)])
        blocked = self.env["yousentech.booking.event"].with_company(company).search([("company_id","=",company.id),("booking_date","=",booking_date),("state","in",["hold","confirmed","preparing","event","completed"])])
        used={(b.hall_id.id,p.id):b for b in blocked for p in b.period_ids}
        return {"success":True,"api_version":"2.0","data":{"halls":[{"id":h.id,"name":h.name,"periods":[{"id":p.id,"name":p.name,"available":(h.id,p.id) not in used} for p in periods]} for h in halls]}}
