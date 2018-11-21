# -*- coding: utf-8 -*-

import hashlib
import json
import os
import requests

from urllib import parse
from odoo import fields, models, api, _
from  odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    exact_online_uuid = fields.Char()
    exact_online_connect_token = fields.Char(readonly=True)
    exact_online_connected = fields.Boolean(compute='check_exact_online_connected', store=True, readonly=True)
    exact_online_can_connect = fields.Boolean(compute='_exact_check_can_connect')
    exact_online_connection_status = fields.Selection([
        ('none', 'Never connected'),
        ('registered', 'Connector registered, not connect to Exact Online'),
        ('payment', 'Awaiting payment'),
        ('init', 'Connected, initial sync required'),
        ('ok', 'Connected and working'),
        ('exception', 'Connected but not working'),
        ('relink', 'Relinking of Connector required')
    ], default='none', readonly=True)
    exact_online_connection_exception = fields.Text(readonly=True)
    exact_online_master = fields.Selection([
        ('odoo', 'Odoo'),
        ('exact', 'Exact'),
        ('none', 'None')
    ], help="Select Odoo if you do not have any data present in Exact Online\n"
            "Select Exact if your current Odoo environment is empty and you have data present in Exact Online\n"
            "Select None if there is data present in both, then you need to fill out the Exact codes of your customers in Odoo",
        default='odoo')
    exact_online_default_sync_invoices = fields.Boolean('Sync invoices',
                                                        help="If this box is checked, for new contacts, the invoices will be synced instead of the account moves.\n"
                                                             "If you want this for your existing customers in Odoo you need to check the box manually on each contact.")

    # Pre synchronisation checklist
    exact_online_payment_terms = fields.Boolean('Payment terms', readonly=True,
                                                help="Checks if there are any payment terms without an Exact Online code")
    exact_online_journals = fields.Boolean('Journals', readonly=True,
                                           help="Checks if there are any journals without an Exact Online code")
    exact_online_tax_codes = fields.Boolean('Tax codes', readonly=True,
                                            help="Checks if there are any tax codes without an Exact Online code")
    exact_online_accounts = fields.Boolean(readonly=True,
        help="Checks if all the accounts needed are also present in Exact Online, check if the codes match.\n"
             "Be sure to check the Bank and Cash account since these are different by default.")
    exact_online_plan = fields.Selection([
        ('basic', 'Basic'),
        ('standard', 'Standard'),
        ('advanced', 'Advanced'),
    ], default='standard', required=True, readonly=True)

    @api.multi
    def write(self, vals):
        conn_state_payment_before = []
        if 'exact_online_connection_status' in vals and vals['exact_online_connection_status'] != 'payment':
            for company in self:
                if company.exact_online_connection_status == 'payment':
                    conn_state_payment_before += [company.id]
        res = super(ResCompany, self).write(vals)
        for company_id in conn_state_payment_before:
            self.env['exact_online.job'].search([
                ('state', '=', 'except_connector'),
                '|', ('company_id', '=', company_id), ('company_id', '=', False)]
            ).write({
                'state': 'to sync'
            })
        return res

    @api.multi
    def action_exact_check_synchronisation_checklist(self):
        for company in self:
            company.exact_online_payment_terms = self.env['account.payment.term'].search_count(
                [('exact_online_code', '=', False)]) == 0
            company.exact_online_journals = self.env['account.journal'].search_count(
                [('exact_online_code', '=', False)]) == 0
            company.exact_online_tax_codes = self.env['account.tax'].search_count(
                [('exact_online_vat_code', '=', False), ('type_tax_use', 'in', ['sale', 'purchase'])]) == 0

    @api.multi
    def action_open_exact_missing_payment_terms(self):
        action = self.env.ref('account.action_payment_term_form').read()[0]
        action['domain'] = [('exact_online_code', '=', False)]
        action['context'] = {}
        return action

    @api.multi
    def action_open_exact_missing_journals(self):
        action = self.env.ref('account.action_account_journal_form').read()[0]
        action['domain'] = [('exact_online_code', '=', False)]
        action['context'] = {}
        return action

    @api.multi
    def action_open_exact_missing_tax_codes(self):
        action = self.env.ref('account.action_tax_form').read()[0]
        action['domain'] = [('exact_online_vat_code', '=', False), ('type_tax_use', 'in', ['sale', 'purchase'])]
        action['context'] = {}
        return action

    @api.multi
    def action_check_exact_missing_accounts(self):
        success, res = self.call_exact({'check_accounts': True})
        if success:
            if res['missing_odoo']:
                return self.action_open_exact_missing_accounts(res['missing_odoo'])
            else:
                self.exact_online_accounts = True
        else:
            raise ValidationError(res)

    @api.multi
    def action_open_exact_missing_accounts(self, missing_accounts=None):
        action = self.env.ref('account.action_account_form').read()[0]
        if missing_accounts:
            action['domain'] = [('code', 'in', missing_accounts)]
        else:
            action['domain'] = []
        action['context'] = {}
        return action

    @api.multi
    @api.depends('exact_online_payment_terms', 'exact_online_journals', 'exact_online_tax_codes', 'exact_online_accounts')
    def _exact_check_can_connect(self):
        for company in self:
            company.exact_online_can_connect = company.exact_online_payment_terms and company.exact_online_journals and \
                                               company.exact_online_tax_codes and company.exact_online_accounts

    @api.multi
    @api.depends('exact_online_uuid')
    def check_exact_online_connected(self):
        for company in self:
            company.exact_online_connected = bool(company.exact_online_uuid)

    @api.multi
    def action_connect_to_exact_online(self):
        self.ensure_one()
        db_name = self.env.registry.db_name
        params = self.env['ir.config_parameter']
        connector_base_url = params.get_param('exact_online.base_url')
        connector_auth_url = params.get_param('exact_online.auth_url')
        connector_url = parse.urljoin(connector_base_url, connector_auth_url)
        connector_url = connector_url.rstrip('/')
        odoo_url = params.get_param('web.base.url')
        odoo_connect_url = parse.urljoin(odoo_url, '/exact/link')
        data = {
            'return_url': '%s?%s' % (odoo_connect_url, parse.urlencode({'db': db_name}))
        }
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': '%s?%s' % (connector_url, parse.urlencode(data)),
        }

    @api.multi
    def action_relink_to_exact_online(self):
        self.ensure_one()
        params = self.env['ir.config_parameter']
        connector_base_url = params.get_param('exact_online.base_url')
        connector_url = parse.urljoin(connector_base_url, '/exact/relink')
        data = {
            'uuid': self.exact_online_uuid,
            'company': self.id
        }
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': '%s?%s' % (connector_url, parse.urlencode(data)),
        }

    @api.multi
    def call_exact(self, data):
        self.ensure_one()
        params = self.env['ir.config_parameter']
        connector_base_url = params.get_param('exact_online.base_url')
        connector_sync_url = params.get_param('exact_online.sync_url')
        connector_url = parse.urljoin(connector_base_url, connector_sync_url)
        connector_url = connector_url.rstrip('/')
        data.update({
            'uuid': self.exact_online_uuid
        })
        response = requests.post(connector_url, data=json.dumps({'params': data}),
                                 headers={'Content-Type': 'application/json'})
        if response.status_code == 200:
            response = json.loads(response.text).get('result')
            return response and response.get('success'), (response and response.get('message')) or ''
        return False, json.loads(response.text)['message']

    @api.multi
    def check_initial_sync_status(self):
        self.ensure_one()
        if not self.exact_online_connected:
            raise ValidationError(_('You are not connected to Exact Online, please Connect this company to Exact Online.'))
        if self.exact_online_connection_status == 'payment':
            raise ValidationError(_('You have outstanding payments, if this is your first time syncing, you need to pay for the initial setup.'))
        elif self.exact_online_connection_status != 'init':
            raise ValidationError(_('You need to be in the init status to do the initial sync.'))

    @api.multi
    def action_do_initial_partner_sync(self):
        self.check_initial_sync_status()
        self.env.ref('exact_online_connector_client.cron_process_exact_sync_jobs').write({'active': False})
        self.action_initial_partner_sync().run()
        self.env.ref('exact_online_connector_client.cron_process_exact_sync_jobs').write({'active': True})

    @api.multi
    def action_initial_partner_sync(self):
        self.ensure_one()
        jobs = self.env['exact_online.job']
        if self.exact_online_connected:
            if self.exact_online_master == 'odoo':
                for rec in self.env['res.partner'].search([]):
                    jobs |= jobs.create({
                        'res_model': 'res.partner',
                        'res_ids': rec.id,
                        'method': 'create',
                        'company_id': self.id
                    })
        return jobs

    @api.multi
    def action_do_initial_invoice_sync(self):
        self.check_initial_sync_status()
        self.env.ref('exact_online_connector_client.cron_process_exact_sync_jobs').write({'active': False})
        self.action_initial_invoice_sync().run()
        self.env.ref('exact_online_connector_client.cron_process_exact_sync_jobs').write({'active': True})

    @api.multi
    def action_initial_invoice_sync(self):
        self.ensure_one()
        jobs = self.env['exact_online.job']
        if self.exact_online_connected:
            if self.exact_online_master == 'odoo':
                # if self.exact_online_default_sync_invoices:
                #     for rec in self.env['account.invoice'].search([('company_id', '=', self.id), ('exact_online_initial_sync', '=', False)]):
                #         jobs |= jobs.create({
                #             'res_model': 'account.invoice',
                #             'res_ids': rec.id,
                #             'method': 'create',
                #             'company_id': rec.company_id.id
                #         })
                # else:
                domain = [('company_id', '=', self.id), ('exact_online_initial_sync', '=', False)]
                if self.exact_online_plan == 'basic':
                    domain += [('journal_id.type', '=', 'sale')]
                elif self.exact_online_plan == 'standard':
                    domain += [('journal_id.type', 'in', ['sale', 'purchase'])]
                for rec in self.env['account.move'].search(domain, order='date asc'):
                    jobs |= jobs.create({
                        'res_model': 'account.move',
                        'res_ids': rec.id,
                        'method': 'create',
                        'company_id': rec.company_id.id
                    })
        return jobs

    @api.multi
    def action_do_initial_sync(self):
        self.ensure_one()
        self.action_do_initial_partner_sync()
        self.action_do_initial_invoice_sync()
