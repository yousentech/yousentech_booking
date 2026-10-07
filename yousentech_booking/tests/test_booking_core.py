from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase

class TestBookingCore(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company=cls.env.company
        cls.partner=cls.env["res.partner"].create({"name":"Booking Test Customer"})
        cls.period=cls.env["yousentech.booking.period"].create({"name":"Evening","company_id":cls.company.id})
        cls.hall=cls.env["yousentech.booking.hall"].create({"name":"Hall A","company_id":cls.company.id,"capacity":100,"list_price":1000})
        cls.resource=cls.env["yousentech.stay.resource"].create({"name":"Room A","company_id":cls.company.id,"resource_type":"room","capacity":2,"nightly_price":300})

    def _event(self,date="2026-11-01"):
        return self.env["yousentech.booking.event"].create({"company_id":self.company.id,"partner_id":self.partner.id,"booking_date":date,"hall_id":self.hall.id,"period_ids":[(6,0,self.period.ids)]})

    def _stay(self,start,end):
        return self.env["yousentech.stay.booking"].create({"company_id":self.company.id,"partner_id":self.partner.id,"resource_id":self.resource.id,"checkin_date":start,"checkout_date":end})

    def test_event_conflict_and_release(self):
        first=self._event()
        first.action_confirm()
        second=self._event()
        with self.assertRaises(ValidationError):
            second.action_confirm()
        first.action_cancel("Test cancellation")
        second.action_confirm()
        self.assertEqual(second.state,"confirmed")

    def test_direct_state_write_is_blocked(self):
        event=self._event("2026-11-02")
        with self.assertRaises(ValidationError):
            event.write({"state":"confirmed"})

    def test_stay_overlap_and_adjacent(self):
        first=self._stay("2026-11-03","2026-11-05")
        first.action_confirm()
        adjacent=self._stay("2026-11-05","2026-11-07")
        adjacent.action_confirm()
        overlap=self._stay("2026-11-04","2026-11-06")
        with self.assertRaises(ValidationError):
            overlap.action_confirm()

    def test_snapshot_revisions_are_append_only(self):
        event=self._event("2026-11-08")
        event.action_confirm()
        self.assertEqual(event.commercial_snapshot_ids.mapped("revision"),[1])
        snap=event.commercial_snapshot_ids
        with self.assertRaises(UserError):
            snap.write({"amount_total":999})
        with self.assertRaises(UserError):
            snap.unlink()
        event.action_cancel("Reprice")
        event.action_reopen()
        event.action_confirm()
        self.assertEqual(sorted(event.commercial_snapshot_ids.mapped("revision")),[1,2])

    def test_invalid_stay_dates(self):
        with self.assertRaises(ValidationError):
            self._stay("2026-11-10","2026-11-10")
