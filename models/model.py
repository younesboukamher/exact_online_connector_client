# -*- coding: utf-8 -*-

from lxml import etree
from odoo import models, api, _


class BaseModel(models.AbstractModel):
    _inherit = 'base'

    @api.model
    def exact_fields_to_monitor(self):
        return []

    @api.model
    def exact_check_implemented(self):
        if len(self) > 1:
            rec = self[0]
        else:
            rec = self
        if not hasattr(rec, 'exact_online_state') or not hasattr(rec, 'exact_online_initial_sync'):
            return False
        if rec._fields['exact_online_state'].related or rec._fields['exact_online_initial_sync'].related:
            return False
        return True

    @api.multi
    def exact_get_company(self):
        if self._context.get('company_id'):
            return self.env['res.company'].browse(self._context.get('company_id'))
        company = self.env.user.company_id
        if self:
            self.ensure_one()
            if 'company_id' in self._fields:
                return getattr(self, 'company_id')
            for field in self._fields:
                if self._fields[field].type == 'many2one' and self._fields[field].comodel_name == 'res.company':
                    return getattr(self, field)
        return company

    @api.model
    def create(self, vals):
        if 'exact_online_state' not in vals and self.exact_check_implemented() and not self._context.get('syncing_exact'):
            vals['exact_online_state'] = 'to sync'
        record = super(BaseModel, self).create(vals)
        if hasattr(record, 'exact_online_state') and record.exact_online_state == 'to sync':
            company_id = record.exact_get_company()
            self.env['exact_online.job'].sudo().create({
                'res_model': self._name,
                'res_ids': record.id,
                'method': 'create',
                'company_id': company_id.id if company_id else False,
            })
        return record

    @api.multi
    def write(self, vals):
        if 'exact_online_state' not in vals and self.exact_check_implemented() and not self._context.get('syncing_exact') and self.ids:
            res_ids = [str(rec.id) for rec in self if rec.exact_online_initial_sync]
            if res_ids:
                fields_to_sync = []
                for v in vals:
                    if v in self.exact_fields_to_monitor() and self._fields[v].type != 'one2many':
                        fields_to_sync.append(v)
                if fields_to_sync:
                    companies = set(self.mapped(lambda r: r.exact_get_company()))
                    for company in companies:
                        res_ids = self.filtered(lambda r: r.exact_get_company() == company).ids
                        self.env['exact_online.job'].sudo().create({
                            'res_model': self._name,
                            'res_ids': ','.join([str(i) for i in res_ids]),
                            'method': 'write',
                            'fields_to_update': ','.join([v for v in fields_to_sync]),
                            'company_id': company.id if company else False
                        })
                    vals['exact_online_state'] = 'to sync'
        return super(BaseModel, self).write(vals)

    @api.multi
    def unlink(self):
        if self.exact_check_implemented() and not self._context.get('syncing_exact') and self.ids:
            for rec in self.filtered(lambda rec: rec.exact_online_initial_sync):
                company_id = rec.exact_get_company()
                self.env['exact_online.job'].sudo().create({
                    'res_model': self._name,
                    'res_ids': rec.id,
                    'method': 'unlink',
                    'company_id': company_id.id if company_id else False,
                })
        return super(BaseModel, self).unlink()

    @api.multi
    def exact_create(self, job_id=None):
        self.ensure_one()
        contexted_self = self.with_context(syncing_exact=True)
        contexted_self.write({
            'exact_online_state': 'syncing'
        })
        company = self.exact_get_company()
        return company.call_exact({
            'model': self._name,
            'action': 'create',
            'data': {
                'res_id': self.id,
                'job_id': job_id
            }
        })

    @api.multi
    def exact_write(self, field_names=None, job_id=None):
        self.ensure_one()
        contexted_self = self.with_context(syncing_exact=True)
        contexted_self.write({
            'exact_online_state': 'syncing'
        })
        company = self.exact_get_company()
        return company.call_exact({
            'model': self._name,
            'action': 'write',
            'data': {
                'res_id': self.id,
                'field_names': field_names or [],
                'job_id': job_id
            }
        })

    @api.model
    def exact_unlink(self, res_id=None, job_id=None):
        company = self.exact_get_company()
        return company.call_exact({
            'model': self._name,
            'action': 'unlink',
            'data': {
                'res_id': res_id,
                'job_id': job_id
            }
        })

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(BaseModel, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if self.exact_check_implemented():
            if view_type == 'form':
                doc = etree.XML(res['arch'])
                button_box = doc.xpath('//div[hasclass("oe_button_box")]')
                if button_box:
                    for node in button_box:
                        button_xml = """
                        <button type="object" name="action_open_exact_sync" class="oe_stat_button" readonly="1" modifiers="{&quot;readonly&quot;: true}">
                            <div class="fa fa-fw o_button_icon">
                                <img src="/exact_online_connector_client/static/description/icon_small.png"/>
                            </div>
                            <div class="o_form_field o_stat_info">
                                <field name="exact_online_state" readonly="1" modifiers="{&quot;readonly&quot;: true}"/>
                            </div>
                        </button>
                        """
                        button_node = etree.fromstring(button_xml)
                        node.append(button_node)
                else:
                    button_xml = """
                        <div class="oe_button_box" name="button_box">
                            <button type="object" name="action_open_exact_sync" class="oe_stat_button" readonly="1" modifiers="{&quot;readonly&quot;: true}">
                                <div class="fa fa-fw o_button_icon">
                                    <img src="/exact_online_connector_client/static/description/icon_small.png"/>
                                </div>
                                <div class="o_form_field o_stat_info">
                                    <field name="exact_online_state" readonly="1" modifiers="{&quot;readonly&quot;: true}"/>
                                </div>
                            </button>
                        </div>
                    """
                    button_node = etree.fromstring(button_xml)
                    for node in doc.xpath('//sheet'):
                        node.insert(0, button_node)
                        break
                res['arch'] = etree.tostring(doc, encoding='unicode')
                res['fields'].update(self.fields_get(['exact_online_state']))
        return res

    @api.multi
    def action_open_exact_sync(self):
        action = self.env.ref('exact_online_connector_client.action_view_exact_online_sync_jobs').read()[0]
        domain = [('res_model', '=', self._name)]
        for i in self.ids:
            domain += [('res_ids', 'ilike', str(i))]
        action['domain'] = domain
        return action
