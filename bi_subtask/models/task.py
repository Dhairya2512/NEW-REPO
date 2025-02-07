# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.


from odoo import api, fields, models, _
from odoo.exceptions import UserError


class res_config_settings(models.TransientModel):
    _inherit = 'res.config.settings'

    warning_child_task = fields.Many2one('project.task.type', 'Prevent stage to change untill all task on same stage')

    @api.model
    def get_values(self):
        res = super(res_config_settings, self).get_values()
        warning_child_task = self.env['ir.config_parameter'].sudo().get_param('bi_subtask.warning_child_task')
        if warning_child_task:
            res.update(
                warning_child_task=int(warning_child_task),

            )
        return res

    def set_values(self):
        res = super(res_config_settings, self).set_values()
        warning_child_task = self.env['ir.config_parameter'].sudo().set_param('bi_subtask.warning_child_task',
                                                                              self.warning_child_task.id)
        return res


class subtask_wizard(models.Model):
    _name = 'subtask.wizard'
    _description = "Subtask Wizard"

    subtask_lines = fields.One2many('project.task', 'wiz_id', string="Task Line")

    def create_subtask(self):
        project_task = self.env['project.task'].sudo().browse(self._context.get('active_id'))
        project = project_task.project_id

        default_stage_id = project.type_ids[:1].id if project.type_ids else False
      

        for task_line in self.subtask_lines:
            vals = {
                'name': task_line.name,  
                'task_parent_id': project_task.id,
                'parent_id': project_task.id,
                'description': task_line.des, 
                'is_subtask': True,
                'project_id': project.id,
            }
            if default_stage_id:
                vals['stage_id'] = default_stage_id
            get_task_id = self.env['project.task'].search([('name','=', task_line.name)],limit=1)
            get_task_id.sudo().write(vals)

        return True


class ProjectTask(models.Model):
    _inherit = "project.task"

    wiz_id = fields.Many2one('subtask.wizard', string="Wiz Parent Id")
    task_parent_id = fields.Many2one('project.task', string="Parent Id",)
    subtask_ids = fields.One2many('project.task', 'task_parent_id', string="Subtask")
    des = fields.Char('Task Description')
    is_subtask = fields.Boolean('Is a subtask')
    set_subtask = fields.Boolean('Get Subtask',default=True)
    planned_hours=fields.Float('Planned hours')
    is_project_task = fields.Boolean(default=True)
    child_ids = fields.One2many('project.task', 'parent_id', string="Sub-tasks", domain=False)


    def cancel_test(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def write(self, vals):
        if vals.get('stage_id'):
            task_type_search = self.env['ir.config_parameter'].sudo().get_param('bi_subtask.warning_child_task')

            if task_type_search:

                if vals.get('stage_id') == int(task_type_search):
                    for task in self.subtask_ids:
                        if task.stage_id.id != int(task_type_search):
                            raise UserError("You can not close parent task until all child tasks are closed.")
                        
        return super(ProjectTask, self).write(vals)

   
