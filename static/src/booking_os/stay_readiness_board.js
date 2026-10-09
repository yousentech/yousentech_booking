/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const TYPES = {room:"غرفة",suite:"جناح",apartment:"شقة",chalet:"شاليه"};
const iso = d => [d.getFullYear(),String(d.getMonth()+1).padStart(2,"0"),String(d.getDate()).padStart(2,"0")].join("-");
const date = s => new Date(s+"T12:00:00");
const add = (d,n) => new Date(d.getFullYear(),d.getMonth(),d.getDate()+n,12);
const BLOCKING = ["hold","confirmed","checked_in","checked_out"];

export class StayReadinessBoard extends Component {
    static template = "yousentech_booking.StayReadinessBoard";
    setup() {
        this.orm=useService("orm");
        this.action=useService("action");
        this.company=useService("company");
        this.state=useState({start:iso(new Date()),nights:1,mode:"day",floor:"all",type:"all",status:"all",query:"",resources:[],bookings:[],holidays:[],loading:true,error:"",selected:null,collapsed:[],detailsTab:'info',filtersOpen:false,assistantOpen:true});
        onWillStart(()=>this.load());
    }
    get holidaysInRange() { return this.state.holidays.filter(h=>h.date>=this.state.start&&h.date<this.end); }
    get weekendDays() { return this.days.filter(d=>[5,6].includes(date(d).getDay())); }
    get days() { return Array.from({length:this.state.nights},(_,i)=>iso(add(date(this.state.start),i))); }
    get end() { return iso(add(date(this.state.start),this.state.nights)); }
    floorLabel(r) { return r.floor_id ? r.floor_id[1] : (r.floor_name || "غير محدد"); }
    get floors() { return [...new Set(this.state.resources.map(r=>this.floorLabel(r)))].sort((a,b)=>a.localeCompare(b,"ar",{numeric:true})); }
    get filtered() {
        const q=this.state.query.trim().toLocaleLowerCase();
        return this.state.resources.filter(r=>(this.state.floor==="all"||this.floorLabel(r)===this.state.floor)&&
            (this.state.type==="all"||r.resource_type===this.state.type)&&(!q||r.name.toLocaleLowerCase().includes(q))&&
            (this.state.status==="all"||this.status(r).key===this.state.status));
    }
    get groups() { return this.floors.map(f=>({name:f,rooms:this.filtered.filter(r=>this.floorLabel(r)===f)})).filter(g=>g.rooms.length); }
    get visibleRooms() { return this.state.resources.filter(r=>(this.state.floor==="all"||this.floorLabel(r)===this.state.floor)&&(this.state.type==="all"||r.resource_type===this.state.type)&&(!this.state.query.trim()||r.name.toLocaleLowerCase().includes(this.state.query.trim().toLocaleLowerCase()))); }
    get counts() {
        const counts={total:this.visibleRooms.length,available:0,occupied:0,reserved:0,maintenance:0,blocked:0,cleaning:0,inspection:0,unknown:0};
        for(const r of this.visibleRooms) {const key=this.status(r).key;if(key in counts)counts[key]++;}
        return counts;
    }
    toggleFloor(f) { this.state.collapsed=this.state.collapsed.includes(f)?this.state.collapsed.filter(x=>x!==f):[...this.state.collapsed,f]; }
    isCollapsed(f) { return this.state.collapsed.includes(f); }
    setStatus(key) { this.state.status=key; }
    resetFilters() { this.state.floor="all";this.state.type="all";this.state.status="all";this.state.query=""; }
    isReady(r) { return this.days.every(d=>this.dayStatus(r,d).key==="available"); }
    statusIcon(key) {return ({available:"fa-check-circle",occupied:"fa-bed",reserved:"fa-calendar-check-o",maintenance:"fa-wrench",blocked:"fa-ban",cleaning:"fa-paint-brush",inspection:"fa-search",unknown:"fa-question-circle"})[key]||"fa-info-circle";}
    get tomorrow() { return iso(add(date(this.state.start),1)); }
    get futureDays() { return Array.from({length:7},(_,i)=>iso(add(date(this.state.start),i))); }
    get afterTomorrow() { return iso(add(date(this.state.start),2)); }
    canReserveOn(r,day) { return ["available","cleaning","inspection","unknown"].includes(this.dayStatus(r,day).key); }
    get forecastSummary() {
        const rooms=this.visibleRooms;
        const count=day=>rooms.filter(r=>this.canReserveOn(r,day)).length;
        return [{day:this.state.start,title:"اليوم",count:count(this.state.start)},
            {day:this.tomorrow,title:"غدًا",count:count(this.tomorrow)},
            {day:this.afterTomorrow,title:"بعد غد",count:count(this.afterTomorrow)}];
    }
    get forecastRooms() { return this.visibleRooms.filter(r=>!this.canReserveOn(r,this.state.start)&&this.canReserveOn(r,this.tomorrow)); }
    readinessHint(r) {
        if(r.housekeeping_state==="clean")return "يلزم التأكد من التجهيز بعد الخروج";
        if(r.housekeeping_state==="dirty")return "تحتاج تنظيفًا قبل التسليم";
        if(r.housekeeping_state==="inspection")return "تحتاج فحصًا قبل التسليم";
        return "يلزم تأكيد التجهيز قبل التسليم";
    }
    checkoutHint(r) {
        const departing=this.roomBookings(r).some(b=>b.checkout_date===this.tomorrow&&b.checkin_date<=this.state.start);
        return departing?"خروج مسجل غدًا":"متاحة للحجز غدًا حسب السجل";
    }
    selectForecast(r) { this.state.selected=r.id;this.state.detailsTab="future"; }
    get selectedBookings() { const r=this.selectedRoom;return r?this.roomBookings(r).filter(b=>b.checkin_date<this.end&&(!b.checkout_date||b.checkout_date>this.state.start)).sort((a,b)=>a.checkin_date.localeCompare(b.checkin_date)):[]; }
    get selectedStatus() { return this.selectedRoom?this.status(this.selectedRoom):null; }
    typeLabel(type) { return TYPES[type] || type; }
    roomBookings(r) {return this.state.bookings.filter(b=>b.resource_id&&b.resource_id[0]===r.id&&BLOCKING.includes(b.state));}
    dayStatus(r,day) {
        const next=iso(add(date(day),1));
        if(r.out_of_service_type&&r.out_of_service_from&&r.out_of_service_from<next&&(!r.out_of_service_to||r.out_of_service_to>day))
            return {key:r.out_of_service_type,label:r.out_of_service_type==="maintenance"?"صيانة":"موقوفة"};
        const match=this.roomBookings(r).find(b=>b.checkin_date<next&&(!b.checkout_date||b.checkout_date>day));
        if(match)return match.state==="checked_in"?{key:"occupied",label:"مشغولة"}:{key:"reserved",label:"محجوزة"};
        if(r.housekeeping_state==="dirty")return {key:"cleaning",label:"تحتاج تنظيفًا"};
        if(r.housekeeping_state==="inspection")return {key:"inspection",label:"بانتظار الفحص"};
        if(r.housekeeping_state==="unknown")return {key:"unknown",label:"التجهيز غير محدد"};
        return {key:"available",label:"شاغرة وجاهزة"};
    }
    status(r) {
        const days=this.days.map(d=>this.dayStatus(r,d));
        return days.find(x=>x.key==="maintenance"||x.key==="blocked")||
            days.find(x=>x.key==="occupied")||days.find(x=>x.key==="reserved")||
            days.find(x=>x.key==="cleaning"||x.key==="inspection"||x.key==="unknown")||
            {key:"available",label:"شاغرة وجاهزة"};
    }
    isBookable(r) {
        return this.days.every(d=>["available","cleaning","inspection","unknown"].includes(this.dayStatus(r,d).key));
    }
    openResource(r) {this.action.doAction({type:"ir.actions.act_window",res_model:"yousentech.stay.resource",res_id:r.id,views:[[false,"form"]],target:"current"});}
    nextDate(r) {
        const future=this.roomBookings(r).filter(b=>!b.checkout_date||b.checkout_date>this.state.start).sort((a,b)=>a.checkin_date.localeCompare(b.checkin_date));
        if(!future.length)return "لا يوجد حجز قادم ضمن أفق البحث";
        const b=future[0];
        return b.checkout_date?"أقرب خروج: "+b.checkout_date:"إقامة مفتوحة";
    }
    async load() {
        this.state.loading=true;this.state.error="";
        try {
            const cid=this.company.currentCompany.id;
            const [resources,bookings,holidays]=await Promise.all([
                this.orm.searchRead("yousentech.stay.resource",[["company_id","=",cid],["active","=",true]],["name","floor_id","floor_name","resource_type","capacity","nightly_price","housekeeping_state","out_of_service_type","out_of_service_from","out_of_service_to","out_of_service_reason"],{order:"sequence,name,id"}),
                this.orm.searchRead("yousentech.stay.booking",[["company_id","=",cid],["checkin_date","<",iso(add(date(this.state.start),Math.max(this.state.nights,32)))],"|",["checkout_date","=",false],["checkout_date",">",this.state.start],["state","in",BLOCKING]],["name","resource_id","checkin_date","checkout_date","state"],{order:"checkin_date,id"}),
                this.orm.searchRead("yousentech.booking.holiday", [["company_id","=",cid],["active","=",true],["date",">=",this.state.start],["date","<",this.end]], ["name","date"], {order:"date,name"}),
            ]);
            this.state.resources=resources;this.state.bookings=bookings;this.state.holidays=holidays;
        } catch(e) {this.state.error="تعذر تحميل بيانات الغرف والحجوزات.";this.state.resources=[];this.state.bookings=[];this.state.holidays=[];}
        finally {this.state.loading=false;}
    }
    async changeStart(ev){if(ev.target.value){this.state.start=ev.target.value;await this.load();}}
    async setMode(mode){this.state.mode=mode;this.state.nights=mode==="week"?7:mode==="month"?30:1;await this.load();}
    async changeNights(ev){const n=Number(ev.target.value);if(Number.isInteger(n)&&n>=1&&n<=31){this.state.nights=n;await this.load();}}
    onFloor(ev){this.state.floor=ev.target.value;}
    onType(ev){this.state.type=ev.target.value;}
    onStatus(ev){this.state.status=ev.target.value;}
    onQuery(ev){this.state.query=ev.target.value;}
    select(r){this.state.selected=this.state.selected===r.id?null:r.id;this.state.detailsTab='info';}
    get selectedRoom(){return this.state.resources.find(r=>r.id===this.state.selected);}
    newBooking(r){if(!this.isBookable(r))return;this.action.doAction({type:"ir.actions.act_window",res_model:"yousentech.stay.booking",views:[[false,"form"]],target:"current",context:{default_resource_id:r.id,default_checkin_date:this.state.start,default_checkout_date:this.end}});}
}
registry.category("actions").add("yousentech_booking.StayReadinessBoard",StayReadinessBoard);
