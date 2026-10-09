/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const DAY = 86400000;
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
        this.state=useState({start:iso(new Date()),nights:1,mode:"day",floor:"all",type:"all",status:"all",query:"",resources:[],bookings:[],loading:true,error:"",selected:null,collapsed:[],detailsTab:'info'});
        onWillStart(()=>this.load());
    }
    get days() { return Array.from({length:this.state.nights},(_,i)=>iso(add(date(this.state.start),i))); }
    get end() { return iso(add(date(this.state.start),this.state.nights)); }
    get floors() { return [...new Set(this.state.resources.map(r=>r.floor_name||"غير محدد"))].sort((a,b)=>a.localeCompare(b,"ar",{numeric:true})); }
    get filtered() {
        const q=this.state.query.trim().toLocaleLowerCase();
        return this.state.resources.filter(r=>(this.state.floor==="all"||(r.floor_name||"غير محدد")===this.state.floor)&&
            (this.state.type==="all"||r.resource_type===this.state.type)&&(!q||r.name.toLocaleLowerCase().includes(q))&&
            (this.state.status==="all"||this.status(r).key===this.state.status));
    }
    get groups() { return this.floors.map(f=>({name:f,rooms:this.filtered.filter(r=>(r.floor_name||"غير محدد")===f)})).filter(g=>g.rooms.length); }
    get counts() {
        const counts={total:this.filtered.length,available:0,occupied:0,reserved:0,maintenance:0,blocked:0,cleaning:0,inspection:0,unknown:0};
        for(const r of this.filtered) {const key=this.status(r).key;if(key in counts)counts[key]++;}
        return counts;
    }
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
        if(!future.length)return "لا يوجد حجز خلال الفترة المعروضة";
        const b=future[0];
        return b.checkout_date?"أقرب خروج: "+b.checkout_date:"إقامة مفتوحة";
    }
    async load() {
        this.state.loading=true;this.state.error="";
        try {
            const cid=this.company.currentCompany.id;
            const [resources,bookings]=await Promise.all([
                this.orm.searchRead("yousentech.stay.resource",[["company_id","=",cid],["active","=",true]],["name","floor_name","resource_type","capacity","nightly_price","housekeeping_state","out_of_service_type","out_of_service_from","out_of_service_to","out_of_service_reason"],{order:"sequence,name,id"}),
                this.orm.searchRead("yousentech.stay.booking",[["company_id","=",cid],["checkin_date","<",this.end],"|",["checkout_date","=",false],["checkout_date",">",this.state.start]],["name","resource_id","checkin_date","checkout_date","state"],{order:"checkin_date,id"}),
            ]);
            this.state.resources=resources;this.state.bookings=bookings;
        } catch(e) {this.state.error="تعذر تحميل بيانات الغرف والحجوزات.";this.state.resources=[];this.state.bookings=[];}
        finally {this.state.loading=false;}
    }
    async changeStart(ev){if(ev.target.value){this.state.start=ev.target.value;await this.load();}}
    async setMode(mode){this.state.mode=mode;this.state.nights=mode==="week"?7:mode==="month"?30:1;await this.load();}
    async changeNights(ev){const n=Number(ev.target.value);if(Number.isInteger(n)&&n>=1&&n<=31){this.state.nights=n;await this.load();}}
    onFloor(ev){this.state.floor=ev.target.value;}
    onType(ev){this.state.type=ev.target.value;}
    onStatus(ev){this.state.status=ev.target.value;}
    onQuery(ev){this.state.query=ev.target.value;}
    select(r){this.state.selected=this.state.selected===r.id?null:r.id;}
    get selectedRoom(){return this.state.resources.find(r=>r.id===this.state.selected);}
    newBooking(r){if(!this.isBookable(r))return;this.action.doAction({type:"ir.actions.act_window",res_model:"yousentech.stay.booking",views:[[false,"form"]],target:"current",context:{default_resource_id:r.id,default_checkin_date:this.state.start,default_checkout_date:this.end}});}
}
registry.category("actions").add("yousentech_booking.StayReadinessBoard",StayReadinessBoard);
