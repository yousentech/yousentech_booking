from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class StayFloor(models.Model):
    _name = "yousentech.stay.floor"
    _description = "Hotel Floor"
    _order = "company_id, sequence, name"

    name = fields.Char(string="اسم الطابق", required=True)
    sequence = fields.Integer(string="الترتيب", default=10)
    company_id = fields.Many2one("res.company", string="الشركة / الفرع", required=True, default=lambda self: self.env.company, index=True)
    active = fields.Boolean(default=True)
    room_ids = fields.One2many("yousentech.stay.resource", "floor_id", string="الغرف")
    room_count = fields.Integer(string="عدد الغرف", compute="_compute_room_count")

    _sql_constraints = [
        ("stay_floor_company_name_unique", "unique(company_id, name)", "اسم الطابق مستخدم مسبقًا في نفس الشركة.")
    ]

    @api.depends("room_ids")
    def _compute_room_count(self):
        for floor in self:
            floor.room_count = len(floor.room_ids)

    @api.constrains("name")
    def _check_name(self):
        for floor in self:
            if not floor.name or not floor.name.strip():
                raise ValidationError(_("يجب إدخال اسم الطابق."))
