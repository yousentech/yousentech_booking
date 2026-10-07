/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class BookingOS extends Component {
    static template = "yousentech_booking.BookingOS";
    setup() {
        this.orm = useService("orm");
        this.company = useService("company");
        this.state = useState({ events: 0, stays: 0, loading: true });
        onWillStart(async () => {
            const companyId = this.company.currentCompany.id;
            const [events, stays] = await Promise.all([
                this.orm.searchCount("yousentech.booking.event", [["company_id", "=", companyId], ["state", "!=", "cancelled"]]),
                this.orm.searchCount("yousentech.stay.booking", [["company_id", "=", companyId], ["state", "!=", "cancelled"]]),
            ]);
            Object.assign(this.state, { events, stays, loading: false });
        });
    }
}
registry.category("actions").add("yousentech_booking.BookingOS", BookingOS);
