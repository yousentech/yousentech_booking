# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class CarCareBranch(models.Model):
    _name = 'ycc.branch'
    _description = 'Car Care Appointment Branch'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    provisional_minutes = fields.Integer(string='Provisional Hold (Minutes)', default=120, required=True)
    slot_ids = fields.One2many('ycc.slot', 'branch_id', string='Booking Periods')
    exception_ids = fields.One2many('ycc.exception', 'branch_id', string='Date Exceptions')

    @api.constrains('provisional_minutes')
    def _check_minutes(self):
        for rec in self:
            if rec.provisional_minutes < 1:
                raise ValidationError(_('Provisional hold duration must be positive.'))


class CarCareSlot(models.Model):
    _name = 'ycc.slot'
    _description = 'Car Care Booking Period'
    _order = 'branch_id, start_hour'

    branch_id = fields.Many2one('ycc.branch', required=True, ondelete='cascade')
    name = fields.Char(compute='_compute_name', store=True)
    start_hour = fields.Float(required=True, string='From Hour')
    end_hour = fields.Float(required=True, string='To Hour')
    capacity = fields.Integer(default=4, required=True)
    active = fields.Boolean(default=True)
    weekday_ids = fields.Many2many('ycc.weekday', string='Operating Days')

    @api.depends('start_hour', 'end_hour')
    def _compute_name(self):
        for rec in self:
            def clock(v):
                minutes = round(v * 60)
                return '%02d:%02d' % (minutes // 60, minutes % 60)
            rec.name = '%s - %s' % (clock(rec.start_hour), clock(rec.end_hour))

    @api.constrains('start_hour', 'end_hour', 'capacity', 'branch_id', 'weekday_ids', 'active')
    def _validate_slot(self):
        for rec in self:
            if not (0 <= rec.start_hour < rec.end_hour <= 24):
                raise ValidationError(_('Invalid period hours.'))
            if rec.capacity < 1:
                raise ValidationError(_('Capacity must be at least one vehicle.'))
            if not rec.active:
                continue
            others = self.search([('branch_id', '=', rec.branch_id.id), ('active', '=', True), ('id', '!=', rec.id)])
            own_days = set(rec.weekday_ids.ids) or set(self.env['ycc.weekday'].search([]).ids)
            for other in others:
                other_days = set(other.weekday_ids.ids) or set(self.env['ycc.weekday'].search([]).ids)
                if own_days & other_days and rec.start_hour < other.end_hour and other.start_hour < rec.end_hour:
                    raise ValidationError(_('Booking periods overlap for the same branch and operating days.'))

    def operates_on(self, day):
        self.ensure_one()
        return not self.weekday_ids or str(day.weekday()) in self.weekday_ids.mapped('code')


class CarCareWeekday(models.Model):
    _name = 'ycc.weekday'
    _description = 'Weekday'
    _order = 'code'
    name = fields.Char(required=True)
    code = fields.Selection([(str(i), str(i)) for i in range(7)], required=True)


class CarCareException(models.Model):
    _name = 'ycc.exception'
    _description = 'Car Care Date Exception'
    branch_id = fields.Many2one('ycc.branch', required=True, ondelete='cascade')
    date = fields.Date(required=True)
    slot_id = fields.Many2one('ycc.slot', string='Affected Period (blank means whole day)')
    reason = fields.Char(required=True)

    @api.constrains('slot_id', 'branch_id')
    def _check_branch(self):
        for rec in self:
            if rec.slot_id and rec.slot_id.branch_id != rec.branch_id:
                raise ValidationError(_('Period must belong to the same branch.'))


class CarCareService(models.Model):
    _name = 'ycc.service'
    _description = 'Car Care Service'
    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    estimated_hours = fields.Float(default=2.0)
    price = fields.Float()


class CarCareAppointment(models.Model):
    _name = 'ycc.appointment'
    _description = 'Car Care Appointment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(default='New', readonly=True, copy=False)
    branch_id = fields.Many2one('ycc.branch', required=True, tracking=True)
    slot_id = fields.Many2one('ycc.slot', required=True, tracking=True)
    date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    partner_id = fields.Many2one('res.partner', required=True, tracking=True)
    phone = fields.Char()
    vehicle_plate = fields.Char(required=True, string='Plate Number')
    vehicle_model = fields.Char(required=True)
    service_id = fields.Many2one('ycc.service', required=True)
    agent_id = fields.Many2one('res.users', default=lambda self: self.env.user)
    notes = fields.Text()
    state = fields.Selection([
        ('provisional', 'Provisional'), ('contacting', 'Contacting'),
        ('confirmed', 'Confirmed'), ('expired', 'Expired'),
        ('cancelled', 'Cancelled'), ('done', 'Arrived'), ('no_show', 'No Show')
    ], default='provisional', required=True, tracking=True)
    hold_until = fields.Datetime(readonly=True, copy=False)
    contact_ids = fields.One2many('ycc.contact', 'appointment_id')
    next_contact_at = fields.Datetime()
    company_id = fields.Many2one('res.company', related='branch_id.company_id', store=True, readonly=True)

    def _occupies(self, now=None):
        self.ensure_one()
        now = now or fields.Datetime.now()
        return self.state in ('confirmed', 'done') or (
            self.state in ('provisional', 'contacting') and self.hold_until and
            fields.Datetime.from_string(self.hold_until) > fields.Datetime.from_string(now))

    def _validate_capacity(self):
        now = fields.Datetime.now()
        for rec in self:
            if not rec.slot_id.active or rec.slot_id.branch_id != rec.branch_id:
                raise ValidationError(_('The selected period is not active in this branch.'))
            day = fields.Date.from_string(rec.date)
            if not rec.slot_id.operates_on(day):
                raise ValidationError(_('This period does not operate on the selected day.'))
            if self.env['ycc.exception'].search_count([
                ('branch_id', '=', rec.branch_id.id), ('date', '=', rec.date),
                '|', ('slot_id', '=', False), ('slot_id', '=', rec.slot_id.id)]):
                raise ValidationError(_('This period is closed by an exception.'))
            # Serialize concurrent reservations for the same branch/period/day.
            key = '%s:%s:%s' % (rec.branch_id.id, rec.slot_id.id, rec.date)
            self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', [key])
            others = self.search([
                ('branch_id', '=', rec.branch_id.id), ('slot_id', '=', rec.slot_id.id),
                ('date', '=', rec.date), ('id', '!=', rec.id),
                ('state', 'in', ['provisional', 'contacting', 'confirmed', 'done'])
            ])
            occupied = sum(1 for b in others if b._occupies(now))
            if rec._occupies(now) and occupied >= rec.slot_id.capacity:
                raise ValidationError(_('Period capacity is full.'))

    @api.model
    def create(self, vals):
        vals = dict(vals)
        vals['name'] = self.env['ir.sequence'].next_by_code('ycc.appointment') or 'New'
        branch = self.env['ycc.branch'].browse(vals.get('branch_id'))
        state = vals.get('state', 'provisional')
        if state in ('provisional', 'contacting'):
            vals['hold_until'] = fields.Datetime.to_string(
                fields.Datetime.from_string(fields.Datetime.now()) +
                timedelta(minutes=branch.provisional_minutes or 120))
        record = super(CarCareAppointment, self).create(vals)
        record._validate_capacity()
        return record

    def write(self, vals):
        vals = dict(vals)
        # Do not allow UI/RPC callers to arbitrarily prolong a hold.
        if 'hold_until' in vals and not self.env.user.has_group('base.group_system'):
            raise UserError(_('Only administrators can edit the hold expiration.'))
        if vals.get('state') in ('provisional', 'contacting') and 'hold_until' not in vals:
            for rec in self:
                if rec.state not in ('provisional', 'contacting') or not rec._occupies():
                    raise UserError(_('Expired or cancelled holds require a new appointment.'))
        result = super(CarCareAppointment, self).write(vals)
        if set(vals) & {'branch_id', 'slot_id', 'date', 'state', 'hold_until'}:
            self._validate_capacity()
        return result

    def action_contacting(self):
        self.write({'state': 'contacting'})

    def action_confirm(self):
        for rec in self:
            if rec.state not in ('provisional', 'contacting') or not rec._occupies():
                raise UserError(_('Only a valid active provisional appointment can be confirmed.'))
            rec.write({'state': 'confirmed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_no_show(self):
        self.write({'state': 'no_show'})

    @api.model
    def cron_expire_holds(self):
        now = fields.Datetime.now()
        self.search([
            ('state', 'in', ['provisional', 'contacting']),
            ('hold_until', '!=', False), ('hold_until', '<=', now)
        ]).write({'state': 'expired'})


class CarCareContact(models.Model):
    _name = 'ycc.contact'
    _description = 'Appointment Contact History'
    _order = 'contact_at desc, id desc'

    appointment_id = fields.Many2one('ycc.appointment', required=True, ondelete='cascade')
    contact_at = fields.Datetime(required=True, default=fields.Datetime.now)
    user_id = fields.Many2one('res.users', required=True, default=lambda self: self.env.user)
    channel = fields.Selection([('call', 'Phone'), ('whatsapp', 'WhatsApp'), ('sms', 'SMS'), ('other', 'Other')], required=True, default='call')
    result = fields.Selection([('no_answer', 'No Answer'), ('follow_up', 'Follow Up'), ('reschedule', 'Reschedule'), ('confirmed', 'Confirmed'), ('other', 'Other')], required=True, default='follow_up')
    note = fields.Text(required=True)
    next_contact_at = fields.Datetime()
