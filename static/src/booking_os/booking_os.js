/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const DAY_MS = 86400000;
const STATES = {
    draft: { label: "مسودة", cls: "draft" },
    hold: { label: "حجز مؤقت", cls: "hold" },
    confirmed: { label: "مؤكد", cls: "confirmed" },
    preparing: { label: "قيد التجهيز", cls: "preparing" },
    event: { label: "الفعالية قائمة", cls: "event" },
    completed: { label: "مكتمل", cls: "completed" },
};

export class BookingOS extends Component {
    static template = "yousentech_booking.BookingOS";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.company = useService("company");
        const today = new Date();
        this.state = useState({
            loading: true,
            anchor: new Date(today.getFullYear(), today.getMonth(), today.getDate()),
            halls: [],
            events: [],
            periods: [],
            query: "",
            hallId: "all",
            stats: { today: 0, holds: 0, conflicts: 0, total: 0 },
        });
        onWillStart(() => this.loadBoard());
    }

    iso(date) {
        const y = date.getFullYear();
        const m = String(date.getMonth() + 1).padStart(2, "0");
        const d = String(date.getDate()).padStart(2, "0");
        return `${y}-${m}-${d}`;
    }

    get weekDays() {
        const anchor = this.state.anchor;
        const day = anchor.getDay();
        const saturdayOffset = day === 6 ? 0 : -(day + 1);
        const start = new Date(anchor.getTime() + saturdayOffset * DAY_MS);
        return Array.from({ length: 7 }, (_, i) => new Date(start.getTime() + i * DAY_MS));
    }

    get visibleHalls() {
        const q = this.state.query.trim().toLowerCase();
        return this.state.halls.filter((h) => (this.state.hallId === "all" || Number(this.state.hallId) === h.id) && (!q || h.name.toLowerCase().includes(q)));
    }

    get monthTitle() {
        return new Intl.DateTimeFormat("ar-SA", { month: "long", year: "numeric" }).format(this.state.anchor);
    }

    gregorian(day) {
        return new Intl.DateTimeFormat("ar-SA", { weekday: "short", day: "numeric", month: "short" }).format(day);
    }

    hijri(day) {
        try {
            return new Intl.DateTimeFormat("ar-SA-u-ca-islamic-umalqura", { day: "numeric", month: "short", year: "numeric" }).format(day);
        } catch {
            return "";
        }
    }

    isToday(day) {
        return this.iso(day) === this.iso(new Date());
    }

    eventsFor(hall, day) {
        const date = this.iso(day);
        return this.state.events.filter((e) => e.hall_id && e.hall_id[0] === hall.id && e.booking_date === date);
    }

    eventClass(event) {
        return STATES[event.state]?.cls || "draft";
    }

    eventLabel(event) {
        return STATES[event.state]?.label || event.state;
    }

    async loadBoard() {
        this.state.loading = true;
        const companyId = this.company.currentCompany.id;
        const days = this.weekDays;
        const from = this.iso(days[0]);
        const to = this.iso(days[6]);
        const [halls, periods, events] = await Promise.all([
            this.orm.searchRead("yousentech.booking.hall", [["company_id", "=", companyId], ["active", "=", true]], ["name", "capacity", "sequence"], { order: "sequence,id" }),
            this.orm.searchRead("yousentech.booking.period", [["company_id", "=", companyId], ["active", "=", true]], ["name", "sequence"], { order: "sequence,id" }),
            this.orm.searchRead("yousentech.booking.event", [["company_id", "=", companyId], ["booking_date", ">=", from], ["booking_date", "<=", to], ["state", "!=", "cancelled"]], ["name", "partner_id", "booking_date", "hall_id", "period_ids", "state", "amount_total"], { order: "booking_date,id" }),
        ]);
        const today = this.iso(new Date());
        Object.assign(this.state, {
            halls, periods, events,
            stats: {
                today: events.filter((e) => e.booking_date === today).length,
                holds: events.filter((e) => e.state === "hold").length,
                conflicts: 0,
                total: events.length,
            },
            loading: false,
        });
    }

    async shiftWeek(delta) {
        this.state.anchor = new Date(this.state.anchor.getTime() + delta * 7 * DAY_MS);
        await this.loadBoard();
    }

    async goToday() {
        const now = new Date();
        this.state.anchor = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        await this.loadBoard();
    }

    onSearch(ev) { this.state.query = ev.target.value; }
    onHallFilter(ev) { this.state.hallId = ev.target.value; }

    openEvent(event) {
        this.action.doAction({ type: "ir.actions.act_window", res_model: "yousentech.booking.event", res_id: event.id, views: [[false, "form"]], target: "current" });
    }

    newBooking(hallId = false, day = false) {
        const context = { default_company_id: this.company.currentCompany.id };
        if (hallId) context.default_hall_id = hallId;
        if (day) context.default_booking_date = this.iso(day);
        this.action.doAction({ type: "ir.actions.act_window", res_model: "yousentech.booking.event", views: [[false, "form"]], target: "current", context });
    }
}
registry.category("actions").add("yousentech_booking.BookingOS", BookingOS);
