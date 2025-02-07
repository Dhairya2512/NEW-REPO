# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import time
from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.tools.sql import drop_view_if_exists
from odoo.exceptions import UserError, ValidationError


class HrTimesheetSheet(models.Model):
    _name = "hr_timesheet_sheet.sheet"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _table = 'hr_timesheet_sheet_sheet'
    _order = "id desc"
    _description = "Timesheet"

    def _default_date_from(self):
        user = self.env['res.users'].browse(self.env.uid)
        r = user.company_id and user.company_id.timesheet_range or 'month'
        if r == 'month':
            return time.strftime('%Y-%m-01')
        elif r == 'week':
            return (datetime.today() + relativedelta(weekday=0, days=-6)).strftime('%Y-%m-%d')
        elif r == 'year':
            return time.strftime('%Y-01-01')
        return fields.Date.context_today(self)

    def _default_date_to(self):
        user = self.env['res.users'].browse(self.env.uid)
        r = user.company_id and user.company_id.timesheet_range or 'month'
        if r == 'month':
            return (datetime.today() + relativedelta(months=+1, day=1, days=-1)).strftime('%Y-%m-%d')
        elif r == 'week':
            return (datetime.today() + relativedelta(weekday=6)).strftime('%Y-%m-%d')
        elif r == 'year':
            return time.strftime('%Y-12-31')
        return fields.Date.context_today(self)

    def _default_employee(self):
        emp_ids = self.env['hr.employee'].search([('user_id', '=', self.env.uid)])
        return emp_ids and emp_ids[0] or False

    name = fields.Char(string="Note")
    employee_id = fields.Many2one('hr.employee', string='Employee', default=_default_employee, required=True)
    user_id = fields.Many2one('res.users', related='employee_id.user_id', string='User', store=True, readonly=True)
    date_from = fields.Date(string='Date From', default=_default_date_from, required=True,
                            index=True, readonly=True)
    date_to = fields.Date(string='Date To', default=_default_date_to, required=True,
                          index=True, readonly=True)
    timesheet_ids = fields.One2many('account.analytic.line', 'sheet_id', store=True, index=True,
                                    string='Timesheet lines')
    # state is created in 'new', automatically goes to 'draft' when created. Then 'new' is never used again ...
    # (=> 'new' is completely useless)
    state = fields.Selection([
        ('new', 'New'),
        ('draft', 'Open'),
        ('confirm', 'Waiting Approval'),
        ('done', 'Approved')], default='new',
        string='Status', required=True, readonly=True, index=True,
        help=' * The \'Open\' status is used when a user is encoding a new and unconfirmed timesheet. '
             '\n* The \'Waiting Approval\' status is used to confirm the timesheet by user. '
             '\n* The \'Approved\' status is used when the users timesheet is accepted by his/her senior.')
    account_ids = fields.One2many('hr_timesheet_sheet.sheet.account', 'sheet_id', string='Analytic accounts',
                                  readonly=True)
    company_id = fields.Many2one('res.company', string='Company')
    department_id = fields.Many2one('hr.department', string='Department')
    total_timesheet_time = fields.Float(string='Total Timesheet Time', compute="_compute_total_time")

    @api.onchange('date_from', 'date_to')
    def onchange_check_date(self):
        for rec in self:
            if rec.date_to < rec.date_from:
                return {
                    'warning': {
                        'title': _('Warning'),
                        'message': _('Please check date format')
                    }
                }

    def _compute_total_time(self):
        for res in self:
            total = 0.0
            for line in res.timesheet_ids:
                total = line.unit_amount + total
            res.total_timesheet_time = total

    @api.constrains('date_to', 'date_from', 'employee_id')
    def _check_sheet_date(self, forced_user_id=False):
        for sheet in self:
            new_user_id = forced_user_id or sheet.user_id and sheet.user_id.id
            if new_user_id:
                self.env.cr.execute('''
					SELECT id
					FROM hr_timesheet_sheet_sheet
					WHERE (date_from <= %s and %s <= date_to)
						AND user_id=%s
						AND id <> %s''',
                                    (sheet.date_to, sheet.date_from, new_user_id, sheet.id))
            # if any(self.env.cr.fetchall()):
            #   raise ValidationError(_('You cannot have 2 timesheets that overlap!\nPlease use the menu \'My Current Timesheet\' to avoid this problem.'))

    @api.onchange('employee_id')
    def onchange_employee_id(self):
        if self.employee_id:
            self.department_id = self.employee_id.department_id
            self.user_id = self.employee_id.user_id

    def copy(self, *args, **argv):
        raise UserError(_('You cannot duplicate a timesheet.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'employee_id' in vals:
                if not self.env['hr.employee'].browse(vals['employee_id']).user_id:
                    raise UserError(
                        _('In order to create a timesheet for this employee, you must link him/her to a user.'))
        res = super(HrTimesheetSheet, self).create(vals_list)
        res.write({'state': 'draft'})
        return res

    def write(self, vals):
        if 'employee_id' in vals:
            new_user_id = self.env['hr.employee'].browse(vals['employee_id']).user_id.id
            if not new_user_id:
                raise UserError(_('In order to create a timesheet for this employee, you must link him/her to a user.'))
            self._check_sheet_date(forced_user_id=new_user_id)
        try:
            return super(HrTimesheetSheet, self).write(vals)
        except:
            return

    def action_timesheet_draft(self):
        notification = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': None,
                'type': None,
                'sticky': False,
            },
        }
        if not self.env.user.has_group('hr_timesheet.group_hr_timesheet_user'):
            raise UserError(_('Only an HR Officer or Manager can refuse timesheets or reset them to draft.'))
        find_manger_id = self.employee_id.parent_id.user_id or self.employee_id.parent_id
        if find_manger_id:
            if self.env.user.id == find_manger_id.id:
                self.write({'state': 'draft'})
                return True
            else:
                notification['params'].update({
                    'message': _(
                        'You cannot refuse the selected timesheets as they either belong to employees who are not part of your team'),
                    'type': 'warning',
                })
            return notification
        else:
            notification['params'].update({
                'message': _(
                    'You cannot refuse the selected timesheets as they either belong to employees who are not part of your team or link user in manger'),
                'type': 'warning',
            })
            return notification

    def action_timesheet_confirm(self):
        for sheet in self:
            if sheet.employee_id and sheet.employee_id and sheet.employee_id.parent_id.user_id:
                sheet.message_subscribe([sheet.employee_id.parent_id.user_id.partner_id.id])

            sheet.write({'state': 'confirm'})

            message = """<ul class="o_Message_trackingValues mb-0 ps-4">"""
            old_task_description = """<span class="o_TrackingValue_oldValue me-1 px-1 text-muted fw-bold fst-italic">New</span>"""
            message += """<li><div class="o_TrackingValue d-flex align-items-center flex-wrap mb-1" role="group">"""
            message += ("%s") % (old_task_description)
            message += """<i class="o_TrackingValue_separator fa fa-long-arrow-right mx-1 text-600" title="Changed" role="img" aria-label="Changed"></i>"""
            message += ("%s") % (sheet.state)
            message += """<span class="o_TrackingValue_oldValue me-1 px-1 text-muted fw-bold fst-italic"> (Status)</span>"""
            message += """</div></li></ul>"""

            user = self.env.user
            if sheet.employee_id.parent_id.user_id:
                notification_ids = [(0, 0,
                                     {
                                         'res_partner_id': sheet.employee_id.parent_id.user_id.partner_id.id,
                                         'notification_type': 'inbox',
                                     }
                                     )]
            else:
                notification_ids = False
            self.env['mail.message'].create({
                'message_type': "user_notification",
                'body': message,
                'subject': "Waiting For Approval",
                'partner_ids': sheet.employee_id.parent_id.user_id.partner_id.ids or False,
                'model': self._name,
                'res_id': self.id,
                'notification_ids': notification_ids,
                'email_from': self.env.user.email_formatted,
                'reply_to': self.env.user.email_formatted,
                'email_layout_xmlid': 'mail.mail_notification_layout',
                'author_id': self.employee_id.user_id.partner_id and self.employee_id.user_id.partner_id.id
            })
        return True

    def action_timesheet_done(self):
        notification = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': None,
                'type': None,
                'sticky': False,
            },
        }
        if not self.env.user.has_group('hr_timesheet.group_hr_timesheet_user'):
            raise UserError(_('Only an HR Officer or Manager can approve timesheets.'))
        if self.filtered(lambda sheet: sheet.state != 'confirm'):
            raise UserError(_("Cannot approve a non-submitted timesheet."))
        find_manger_id = self.employee_id.parent_id.user_id or self.employee_id.parent_id
        if find_manger_id:
            if self.env.user.id == find_manger_id.id:
                self.write({'state': 'done'})
                return True
            else:
                notification['params'].update({
                    'message': _(
                        'You cannot validate the selected timesheets as they either belong to employees who are not part of your team'),
                    'type': 'warning',
                })
            return notification
        else:
            notification['params'].update({
                'message': _(
                    'You cannot validate the selected timesheets as they either belong to employees who are not part of your team or link user in manger'),
                'type': 'warning',
            })
            return notification

    @api.depends('date_from')
    def _compute_display_name(self):
        week_count = [(r['id'], _('Week ') + str(datetime.strptime(str(r['date_from']), '%Y-%m-%d').isocalendar()[1]))
                      for r in self.read(['date_from'], load='_classic_write')]
        get_name = week_count[0]
        self.display_name = get_name[1]

    def unlink(self):
        sheets = self.read(['state'])
        for sheet in sheets:
            if sheet['state'] in ('confirm', 'done'):
                raise UserError(_('You cannot delete a timesheet which is already confirmed.'))

        analytic_timesheet_toremove = self.env['account.analytic.line']
        for sheet in self:
            analytic_timesheet_toremove += sheet.timesheet_ids.filtered(lambda t: not t.task_id)
        analytic_timesheet_toremove.unlink()

        return super(HrTimesheetSheet, self).unlink()

    def _track_subtype(self, init_values):
        if self:
            record = self[0]
            if 'state' in init_values and record.state == 'confirm':
                return self.env.ref('bi_hr_timesheet_sheet.mt_timesheet_confirmed')
            elif 'state' in init_values and record.state == 'done':
                return self.env.ref('bi_hr_timesheet_sheet.mt_timesheet_approved')
        return super(HrTimesheetSheet, self)._track_subtype(init_values)

    @api.model
    def _needaction_domain_get(self):
        empids = self.env['hr.employee'].search([('parent_id.user_id', '=', self.env.uid)])
        if not empids:
            return False
        return ['&', ('state', '=', 'confirm'), ('employee_id', 'in', empids.ids)]


class HrTimesheetSheetSheetAccount(models.Model):
    _name = "hr_timesheet_sheet.sheet.account"
    _description = "Timesheets by Period"
    _auto = False
    _order = 'name'

    name = fields.Many2one('account.analytic.account', string='Project / Analytic Account', readonly=True)
    sheet_id = fields.Many2one('hr_timesheet_sheet.sheet', string='Sheet', readonly=True)
    total = fields.Float('Total Time', digits=(16, 2), readonly=True)

    _depends = {
        'account.analytic.line': ['account_id', 'date', 'unit_amount', 'user_id'],
        'hr_timesheet_sheet.sheet': ['date_from', 'date_to', 'user_id'],
    }

    @api.model
    def init(self):
        drop_view_if_exists(self._cr, 'hr_timesheet_sheet_sheet_account')
        self._cr.execute("""create view hr_timesheet_sheet_sheet_account as (
			select
				min(l.id) as id,
				l.account_id as name,
				s.id as sheet_id,
				sum(l.unit_amount) as total
			from
				account_analytic_line l
					LEFT JOIN hr_timesheet_sheet_sheet s
						ON (s.date_to >= l.date
							AND s.date_from <= l.date
							AND s.user_id = l.user_id)
			group by l.account_id, s.id
		)""")
