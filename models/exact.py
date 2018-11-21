# -*- coding: utf-8 -*-

import logging
from odoo import fields, models, api, _


_logger = logging.getLogger(__name__)


class ExactOnlineJob(models.Model):
    _name = 'exact_online.job'
    _order = 'create_date asc, id asc'

    create_date = fields.Datetime(string='Creation Date', readonly=True, index=True)
    company_id = fields.Many2one('res.company')
    state = fields.Selection([
        ('to sync', 'To sync'),
        ('syncing', 'Syncing'),
        ('except_odoo', 'Exception @ Odoo'),
        ('except_exact', 'Exception @ Exact'),
        ('except_connector', 'Exception @ Connector')
    ], default='to sync')
    res_model = fields.Char('Model to update')
    res_ids = fields.Char('IDs to update', help='IDs used for update (separated by commas)')
    fields_to_update = fields.Char(help='Fields to update (separated by commas)')
    exception = fields.Text()
    method = fields.Selection([
        ('create', 'Create'),
        ('write', 'Update'),
        ('unlink', 'Delete')
    ])

    @api.multi
    def re_run(self):
        self.filtered(lambda j: j.state != 'syncing').write({'state': 'to sync'})
        self.run()

    @api.multi
    def run(self):
        self.write({'exception': False})
        for job in self.filtered(lambda j: j.state == 'to sync'):
            companies = job.company_id
            if not companies:
                companies = self.env['res.company'].search([('exact_online_connected', '=', True)])
            if companies.filtered(lambda c: c.exact_online_connection_status == 'payment'):
                job.write({
                    'state': 'except_connector',
                    'exception': _('You have outstanding payments that need to be made for the connector to operate.'
                                   'Please contact Callista (https://callista.be/page/contactus) for more information.')
                })
                self.env.cr.commit()
            else:
                for company in companies:
                    model_obj = self.env[job.res_model].with_context(company_id=company.id, force_company=company.id)
                    res_ids = [int(float(i)) for i in job.res_ids.split(',')]
                    if job.method == 'unlink':
                        success = True
                        message = ''
                        for res_id in res_ids:
                            success, message = model_obj.exact_unlink(res_id, job.id)
                        if not success:
                            job.write({
                                'state': 'except_odoo',
                                'exception': message
                            })
                        else:
                            job.write({
                                'state': 'syncing'
                            })
                    else:
                        records = model_obj.browse(res_ids)
                        for record in records.exists():
                            if job.method == 'create':
                                success, message = record.exact_create(job.id)
                            elif job.method == 'write':
                                success, message = record.exact_write(job.fields_to_update, job.id)
                            else:
                                success = False
                                message = _('Unknown method: %s') % job.method
                            if not success:
                                job.write({
                                    'state': 'except_odoo',
                                    'exception': message
                                })
                            else:
                                job.write({
                                    'state': 'syncing'
                                })
                    self.env.cr.commit()

    @api.model
    def run_sync_jobs(self):
        jobs_to_run = self.search([('state', '=', 'to sync'), ('exception', '=', False)])
        jobs_to_run.run()
        return True
