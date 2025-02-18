# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.tools import ustr
from odoo.exceptions import UserError, ValidationError

class AccountBudgetPost(models.Model):
	_name = "account.budget.post"
	_order = "name"
	_description = "Budgetary Position"

	name = fields.Char('Name', required=True)
	account_ids = fields.Many2many('account.account', 'account_budget_rel', 'budget_id', 'account_id', 'Accounts',
		domain=[('deprecated', '=', False)])
	crossovered_budget_line = fields.One2many('crossovered.budget.lines', 'general_budget_id', 'Budget Lines')
	company_id = fields.Many2one('res.company', required=True, readonly=True, default=lambda self: self.env.company)

	def _check_account_ids(self, vals):
		if 'account_ids' in vals:
			account_ids = vals['account_ids']
		else:
			account_ids = self.account_ids
		if not account_ids:
			raise ValidationError(_('The budget must have at least one account.'))

	@api.model_create_multi
	def create(self, vals_list):
		for vals in vals_list:
			self._check_account_ids(vals)
		return super(AccountBudgetPost, self).create(vals_list)

	def write(self, vals):
		self._check_account_ids(vals)
		return super(AccountBudgetPost, self).write(vals)


class CrossoveredBudget(models.Model):
	_name = "crossovered.budget"
	_description = "Budget"
	_inherit = ['mail.thread']

	name = fields.Char('Budget Name', required=True)
	creating_user_id = fields.Many2one('res.users', 'Responsible', default=lambda self: self.env.user)
	date_from = fields.Date('Start Date', required=True)
	date_to = fields.Date('End Date', required=True)
	state = fields.Selection([
		('draft', 'Draft'),
		('cancel', 'Cancelled'),
		('confirm', 'Confirmed'),
		('validate', 'Validated'),
		('done', 'Done')
		], 'Status', default='draft', index=True, required=True, readonly=True, copy=False)
	crossovered_budget_line = fields.One2many('crossovered.budget.lines', 'crossovered_budget_id', 'Budget Lines',
		 copy=True)
	company_id = fields.Many2one('res.company', required=True, readonly=True, default=lambda self: self.env.company)
	pertial = fields.Boolean(string='pertial',default=False)
	
	

	@api.onchange('date_to','date_from')
	def _onchange_date(self):
		if self.date_to and self.date_from:
			if self.date_from > self.date_to:
				raise ValidationError(_("Please select a proper date."))

	# @api.model
	# def default_get(self, fields):
	# 	res = super(CrossoveredBudget,self).default_get(fields)
	# 	vals = self.env['res.config.settings'].sudo().search([],limit=1,order="id desc")
	# 	if vals.partial_budget_approve == True:
	# 		res['pertial'] = True
	# 	return res

	def action_budget_confirm(self):
		self.write({'state': 'confirm'})

	def action_budget_draft(self):
		self.write({'state': 'draft'})

	def action_budget_validate(self):
		self.write({'state': 'validate'})

	def action_budget_cancel(self):
		self.write({'state': 'cancel'})

	def action_budget_done(self):
		self.write({'state': 'done'})


class CrossoveredBudgetLines(models.Model):
	_name = "crossovered.budget.lines"
	_description = "Budget Line"
	_rec_name = 'crossovered_budget_id'

	crossovered_budget_id = fields.Many2one('crossovered.budget', 'Budget', ondelete='cascade', index=True, required=True)
	analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account')
	general_budget_id = fields.Many2one('account.budget.post', 'Budgetary Position', required=True)
	date_from = fields.Date('Start Date', required=True)
	date_to = fields.Date('End Date', required=True)
	paid_date = fields.Date('Paid Date')
	planned_amount = fields.Float('Planned Amount', required=True, digits=0)
	practical_amount = fields.Float(compute='_compute_practical_amount', string='Practical Amount', digits=0)
	theoritical_amount = fields.Float(compute='_compute_theoritical_amount', string='Theoretical Amount', digits=0)
	percentage = fields.Float(compute='_compute_percentage', string='Achievement')
	company_id = fields.Many2one(related='crossovered_budget_id.company_id', comodel_name='res.company',
		string='Company', store=True, readonly=True)
	pertial_id = fields.Boolean(related='crossovered_budget_id.pertial')
	pertial_amount = fields.Float(string='Partial Amount')
	currency_id = fields.Many2one(string="Currency", related='company_id.currency_id')

	@api.onchange('date_to','date_from')
	def _onchange_date(self):
		if self.date_to and self.date_from:
			if self.date_from > self.date_to:
				raise ValidationError(_("Please select a proper date."))



	def _compute_practical_amount(self):
		for line in self:
			result = 0.0
			acc_ids = line.general_budget_id.account_ids.ids
			date_to = self.env.context.get('wizard_date_to') or line.date_to
			date_from = self.env.context.get('wizard_date_from') or line.date_from
			if not date_to and not date_from:
				raise ValidationError(_('Please select period first!!!'))

			if line.analytic_account_id.id:
				self.env.cr.execute("""
					SELECT SUM(amount)
					FROM account_analytic_line
					WHERE account_id=%s
						AND (date between to_date(to_char(%s,'yyyy-mm-dd'), 'yyyy-mm-dd') AND to_date(to_char(%s,'yyyy-mm-dd'), 'yyyy-mm-dd'))
						AND general_account_id=ANY(%s)""",
				(line.analytic_account_id.id, date_from, date_to, acc_ids,))
				result = self.env.cr.fetchone()[0] or 0.0
			else:
				self.env.cr.execute("""
					SELECT sum(credit)-sum(debit)
					FROM account_move_line
					WHERE account_id =ANY(%s)
						AND (date between to_date(to_char(%s,'yyyy-mm-dd'), 'yyyy-mm-dd') AND to_date(to_char(%s,'yyyy-mm-dd'), 'yyyy-mm-dd'))""",

				(line.general_budget_id.account_ids.ids, date_from, date_to))
				result = self.env.cr.fetchone()[0] or 0.0
			
			line.practical_amount = result

	def _compute_theoritical_amount(self):
		today = fields.Datetime.now()
		for line in self:
			if self.env.context.get('wizard_date_from') and self.env.context.get('wizard_date_to'):
				date_from = fields.Datetime.from_string(self.env.context.get('wizard_date_from'))
				date_to = fields.Datetime.from_string(self.env.context.get('wizard_date_to'))
				if date_from < fields.Datetime.from_string(line.date_from):
					date_from = fields.Datetime.from_string(line.date_from)
				elif date_from > fields.Datetime.from_string(line.date_to):
					date_from = False

				if date_to > fields.Datetime.from_string(line.date_to):
					date_to = fields.Datetime.from_string(line.date_to)
				elif date_to < fields.Datetime.from_string(line.date_from):
					date_to = False

				theo_amt = 0.00
				if date_from and date_to:
					line_timedelta = fields.Datetime.from_string(line.date_to) - fields.Datetime.from_string(line.date_from)
					elapsed_timedelta = date_to - date_from
					if elapsed_timedelta.days > 0:
						if line.pertial_amount > 0:
							theo_amt = (elapsed_timedelta.total_seconds() / line_timedelta.total_seconds()) * line.pertial_amount
						else:
							theo_amt = (elapsed_timedelta.total_seconds() / line_timedelta.total_seconds()) * line.planned_amount
			else:
				if line.paid_date:
					if fields.Datetime.from_string(line.date_to) <= fields.Datetime.from_string(line.paid_date):
						theo_amt = 0.00
					else:
						if line.pertial_amount > 0:
							theo_amt = line.pertial_amount
						else:
							theo_amt = line.planned_amount
				else:
					line_timedelta = fields.Datetime.from_string(line.date_to) - fields.Datetime.from_string(line.date_from)
					elapsed_timedelta = fields.Datetime.from_string(today) - (fields.Datetime.from_string(line.date_from))

					if elapsed_timedelta.days < 0:
						# If the budget line has not started yet, theoretical amount should be zero
						theo_amt = 0.00
					elif line_timedelta.days > 0 and fields.Datetime.from_string(today) < fields.Datetime.from_string(line.date_to):
						if line.pertial_amount > 0:
							theo_amt = (elapsed_timedelta.total_seconds() / line_timedelta.total_seconds()) * line.pertial_amount
						else:
							theo_amt = (elapsed_timedelta.total_seconds() / line_timedelta.total_seconds()) * line.planned_amount
					else:
						if line.pertial_amount > 0:
							theo_amt = line.pertial_amount
						else:
							theo_amt = line.planned_amount

			line.theoritical_amount = theo_amt

	def _compute_percentage(self):
		for line in self:
			if line.theoritical_amount != 0.00:
				line.percentage = float((line.practical_amount or 0.0) / line.theoritical_amount) * 100
			else:
				line.percentage = 0.00
