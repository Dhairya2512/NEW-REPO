# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models,api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    issue_count = fields.Integer(compute='_compute_issue_count', string='# Issues')

    def _compute_issue_count(self):
        Issue = self.env['project.issue']
        for partner in self:
            partner.issue_count = Issue.search_count([('partner_id', 'child_of', partner.commercial_partner_id.id)])



class AccountMove(models.Model):
    _inherit = "account.move"

    job_order_id = fields.Many2one('job.order', string="Job Order")



class Saleorder(models.Model):
    _inherit = "sale.order"

    job_cost_sheet_id = fields.Many2one('job.cost.sheet', string="Job Order")


    def action_confirm(self):
        res = super(Saleorder, self).action_confirm()
        if self.job_cost_sheet_id:
            return {
                "name": "Job Cost Sheet",
                "view_mode": "form",
                "res_model": "job.cost.sheet",
                "res_id": self.job_cost_sheet_id.id,
                "type": "ir.actions.act_window",
                "target": "current",
            }
        return res
