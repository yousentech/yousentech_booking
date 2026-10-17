# -*- coding: utf-8 -*-
from datetime import date, timedelta
from odoo import http, fields
from odoo.http import request
from odoo.exceptions import AccessError


class CarCareCalendar(http.Controller):

    @http.route('/ycc/calendar/data', type='json', auth='user')
    def calendar_data(self, branch_id=None, start=None, end=None):
        Branch = request.env['ycc.branch']
        branches = Branch.search([]).read(['name'])
        if not branches:
            return {'branches': [], 'days': [], 'slots': [], 'appointments': []}
        branch = Branch.browse(int(branch_id)) if branch_id else Branch.browse(branches[0]['id'])
        branch.check_access_rights('read')
        branch.check_access_rule('read')
        if not branch.exists():
            return {'branches': branches, 'days': [], 'slots': [], 'appointments': []}
        first = fields.Date.from_string(start) if start else date.today()
        last = fields.Date.from_string(end) if end else first + timedelta(days=7)
        if last <= first or (last - first).days > 42:
            return {'error': 'Invalid date range'}
        Slot = request.env['ycc.slot']
        Exception = request.env['ycc.exception']
        Appointment = request.env['ycc.appointment']
        slots = Slot.search([('branch_id', '=', branch.id), ('active', '=', True)])
        exceptions = Exception.search([('branch_id', '=', branch.id), ('date', '>=', first), ('date', '<', last)])
        appointments = Appointment.search([
            ('branch_id', '=', branch.id), ('date', '>=', first), ('date', '<', last),
            ('state', 'in', ['provisional', 'contacting', 'confirmed', 'done'])
        ])
        now = fields.Datetime.now()
        slot_data = [{'id': s.id, 'name': s.name, 'capacity': s.capacity,
                      'days': [int(x) for x in s.weekday_ids.mapped('code')]} for s in slots]
        appt_data = []
        for a in appointments:
            if not a._occupies(now):
                continue
            appt_data.append({
                'id': a.id, 'name': a.name, 'date': fields.Date.to_string(a.date),
                'slot_id': a.slot_id.id, 'client': a.partner_id.name,
                'vehicle': '%s · %s' % (a.vehicle_model, a.vehicle_plate),
                'service': a.service_id.name, 'state': a.state,
                'agent': a.agent_id.name or '', 'hold_until': a.hold_until or '',
                'phone': a.phone or '',
            })
        return {
            'branches': branches, 'branch_id': branch.id, 'slots': slot_data,
            'appointments': appt_data,
            'exceptions': [{'date': fields.Date.to_string(e.date),
                            'slot_id': e.slot_id.id or False, 'reason': e.reason} for e in exceptions],
        }
