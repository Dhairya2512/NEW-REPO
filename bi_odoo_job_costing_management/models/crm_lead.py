from odoo import models, fields, api, _

class Lead(models.Model):
    _inherit = "crm.lead"


    job_costing_id = fields.Many2one(
        'job.cost.sheet',
        string='Estimation',
    )
    estimation_count = fields.Integer(string="Estimation Count", compute ="count_of_estimation")
    scope_of_work = fields.Html(string='scope of work')

    def action_open_estimation_form(self):
        self.ensure_one()
        job_costing = self.env['job.cost.sheet'].create({
            'name': self.name,
            'job_issue_customer_id': self.partner_id.id,
            'opportunity_id': self.id,
            'scope_of_work': self.scope_of_work,
        })
        self.job_costing_id = job_costing.id
        return {
                'name': 'Job Costing',
                'view_mode': 'form',
                'res_model': 'job.cost.sheet',
                'res_id': job_costing.id,
                'type': 'ir.actions.act_window',
                'target': 'current',
            }

    def count_of_estimation(self):
        for lead in self:
            lead.estimation_count = self.env['job.cost.sheet'].search_count([
                ('opportunity_id', '=', lead.id)
            ])


    def action_view_estimations(self):
        self.ensure_one()
        return {
            'name': 'Job Costing',
            'view_mode': 'list,form',
            'res_model': 'job.cost.sheet',
            'type': 'ir.actions.act_window',
            'domain': [('opportunity_id', '=', self.id)],
        }
