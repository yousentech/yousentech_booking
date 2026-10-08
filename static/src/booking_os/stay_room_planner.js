/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const DAY = 86400000;
const STATES = {
    draft: ["مسودة", "draft"], hold: ["مؤقت", "hold"],
    confirmed: ["مؤكد", "confirmed"], checked_in: ["تم الدخول", "checked_in"],
    checked_out: ["تم الخروج", "checked_out"], cancelled: ["ملغي", "cancelled"],
};
const TYPE = { room: "غرفة", suite: "جناح", apartment: "شقة", chalet: "شاليه" };
function parseDate(value) { return new Date(value + "T12:00:00"); }
function iso(date) {
    return [date.getFullYear(), String(date.getMonth() + 1).padStart(2, "0"), String(date.getDate()).padStart(2, "0")].join("-");
}
function addDays(date, n) { const d = new Date(date); d.setDate(d.getDate() + n); return d; }
function daysBetween(a, b) { return Math.round((Date.UTC(b.getFullYear(), b.getMonth(), b.getDate()) - Date.UTC(a.getFullYear(), a.getMonth(), a.getDate())) / DAY); }

export class StayRoomPlanner extends Component {
    static template = "yousentech_booking.StayRoomPlanner";
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.company = useService("company");
        this.state = useState({
            anchor: parseDate(iso(new Date())), span: 7, loading: true,
            resources: [], bookings: [], query: "", type: "all",
            selectedId: null, error: "", floor: "all", status: "all", collapsedFloors: [],
        });
        onWillStart(() => this.load());
    }
    get start() { return this.state.anchor; }
    get end() { return addDays(this.start, this.state.span); }
    get days() { return Array.from({length: this.state.span}, (_, i) => addDays(this.start, i)); }
    get dateTitle() {
        const fmt = d => new Intl.DateTimeFormat("ar-SA-u-ca-gregory", {day:"numeric",month:"short",year:"numeric"}).format(d);
        return fmt(this.start) + " — " + fmt(addDays(this.end, -1));
    }
    gregorian(day) { return new Intl.DateTimeFormat("ar-SA-u-ca-gregory", {weekday:"short",day:"numeric",month:"short"}).format(day); }
    hijri(day) {
        try { return new Intl.DateTimeFormat("ar-SA-u-ca-islamic-umalqura", {day:"numeric",month:"short"}).format(day); }
        catch { return ""; }
    }
    isToday(day) { return iso(day) === iso(new Date()); }
    get floors() {
        return [...new Set(this.state.resources.map(r => r.floor_name || "غير محدد"))].sort((a, b) => a.localeCompare(b, "ar", {numeric:true}));
    }
    get roomGroups() {
        return this.floors.filter(f => this.state.floor === "all" || f === this.state.floor)
            .map(f => ({name:f, rooms:this.visibleResources.filter(r => (r.floor_name || "غير محدد") === f),
                collapsed:this.state.collapsedFloors.includes(f)}))
            .filter(g => g.rooms.length);
    }
    toggleFloor(name) {
        this.state.collapsedFloors = this.state.collapsedFloors.includes(name)
            ? this.state.collapsedFloors.filter(f => f !== name)
            : [...this.state.collapsedFloors, name];
    }
    onFloor(ev) { this.state.floor = ev.target.value; }
    onStatus(ev) { this.state.status = ev.target.value; }
    get monthDays() {
        const d = this.start;
        return Array.from({length: 42}, (_, i) => addDays(new Date(d.getFullYear(), d.getMonth(), 1, 12), i - ((new Date(d.getFullYear(), d.getMonth(), 1).getDay() + 1) % 7)));
    }
    get monthLabel() { return new Intl.DateTimeFormat("ar-SA-u-ca-gregory", {month:"long",year:"numeric"}).format(this.start); }
    get hijriRange() {
        try {
            const fmt = d => new Intl.DateTimeFormat("ar-SA-u-ca-islamic-umalqura", {day:"numeric",month:"long",year:"numeric"}).format(d);
            return fmt(this.start) + " — " + fmt(addDays(this.end, -1));
        } catch { return ""; }
    }
    get visibleResources() {
        const q = this.state.query.trim().toLocaleLowerCase();
        return this.state.resources.filter(r =>
            (this.state.type === "all" || r.resource_type === this.state.type) &&
            (this.state.floor === "all" || (r.floor_name || "غير محدد") === this.state.floor) &&
            (!q || r.name.toLocaleLowerCase().includes(q)));
    }
    get selectedBooking() { return this.state.bookings.find(b => b.id === this.state.selectedId); }
    get activeBookings() { return this.state.bookings.filter(b => b.state !== "cancelled"); }
    get stats() {
        const today = iso(new Date());
        const resourceIds = new Set(this.visibleResources.map(r => r.id));
        const bookings = this.activeBookings.filter(b => b.resource_id && resourceIds.has(b.resource_id[0]));
        const occupied = new Set(bookings.filter(b => ["hold", "confirmed", "checked_in", "checked_out"].includes(b.state) && b.checkin_date <= today && (!b.checkout_date || b.checkout_date > today)).map(b => b.resource_id[0]));
        return {
            total: resourceIds.size, available: Math.max(0, resourceIds.size - occupied.size),
            occupied: occupied.size, arrivals: bookings.filter(b => b.checkin_date === today).length,
            departures: bookings.filter(b => b.checkout_date === today).length,
        };
    }
    bookingsFor(resource) {
        return this.activeBookings.filter(b => (this.state.status === "all" || b.state === this.state.status) && b.resource_id && b.resource_id[0] === resource.id &&
            b.checkin_date < iso(this.end) && (!b.checkout_date || b.checkout_date > iso(this.start)))
            .sort((a,b) => a.checkin_date.localeCompare(b.checkin_date) || a.id - b.id);
    }
    barStyle(booking) {
        const first = Math.max(0, daysBetween(this.start, parseDate(booking.checkin_date)));
        const last = booking.checkout_date ? Math.min(this.state.span, daysBetween(this.start, parseDate(booking.checkout_date))) : this.state.span;
        const width = Math.max(1, last - first);
        return `grid-column:${first + 1} / span ${width};`;
    }
    label(state) { return STATES[state]?.[0] || state; }
    stateClass(state) { return STATES[state]?.[1] || "draft"; }
    typeLabel(type) { return TYPE[type] || type; }
    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const companyId = this.company.currentCompany.id;
            const [resources, bookings] = await Promise.all([
                this.orm.searchRead("yousentech.stay.resource",
                    [["company_id","=",companyId],["active","=",true]],
                    ["name","resource_type","capacity","nightly_price","sequence","floor_name"],
                    {order:"sequence,name,id"}),
                this.orm.searchRead("yousentech.stay.booking",
                    [["company_id","=",companyId],["checkin_date","<",iso(this.end)],
                     "|",["checkout_date","=",false],["checkout_date",">",iso(this.start)]],
                    ["name","partner_id","resource_id","checkin_date","checkout_date","state","amount_total"],
                    {order:"checkin_date,id"}),
            ]);
            this.state.resources = resources;
            this.state.bookings = bookings;
            if (this.state.selectedId && !bookings.some(b => b.id === this.state.selectedId)) this.state.selectedId = null;
        } catch (error) {
            this.state.error = "تعذر تحميل مخطط الغرف. تحقق من صلاحياتك أو أعد المحاولة.";
            this.state.resources = [];
            this.state.bookings = [];
        } finally { this.state.loading = false; }
    }
    async move(delta) { this.state.anchor = addDays(this.start, delta * this.state.span); await this.load(); }
    async today() { this.state.anchor = parseDate(iso(new Date())); await this.load(); }
    async setSpan(span) { this.state.span = span; await this.load(); }
    onSearch(ev) { this.state.query = ev.target.value; }
    onType(ev) { this.state.type = ev.target.value; }
    selectBooking(booking) { this.state.selectedId = booking.id; }
    closeDetails() { this.state.selectedId = null; }
    openBooking(booking) {
        this.action.doAction({type:"ir.actions.act_window",res_model:"yousentech.stay.booking",
            res_id:booking.id,views:[[false,"form"]],target:"current"});
    }
    newBooking(resource) {
        this.action.doAction({type:"ir.actions.act_window",res_model:"yousentech.stay.booking",
            views:[[false,"form"]],target:"current",
            context:resource ? {default_resource_id:resource.id,default_checkin_date:iso(this.start)} : {}});
    }
}
registry.category("actions").add("yousentech_booking.StayRoomPlanner", StayRoomPlanner);
