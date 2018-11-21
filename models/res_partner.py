# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def exact_fields_to_monitor(self):
        return [
            'city',
            'comment',
            'country_id',
            'currency_id',
            'customer',
            'email',
            'exact_online_code',
            'lang',
            'name',
            'phone',
            'property_account_payable_id',
            'property_account_receivable_id',
            'property_payment_term_id',
            'property_supplier_payment_term_id',
            'ref',
            'street',
            'street2',
            'supplier',
            'vat',
            'website',
            'zip'
        ]

    exact_online_initial_sync = fields.Boolean()
    exact_online_state = fields.Selection([
        ('synced', 'Synced'),
        ('to sync', 'To sync'),
        ('syncing', 'Syncing'),
        ('sync exception', 'Sync Exception')
    ], default='to sync')
    exact_sync_invoices = fields.Boolean('Exact Online: Sync invoices', default=lambda self: self.env.user.company_id.exact_online_default_sync_invoices)

    @api.model
    def create(self, vals):
        res = super(ResPartner, self).create(vals)
        if res.property_payment_term_id and not res.property_payment_term_id.exact_online_code:
            raise ValidationError(_('Please fill out the Exact Online code for Payment term %s before creating this partner') % res.property_payment_term_id.name)
        if res.property_supplier_payment_term_id and not res.property_supplier_payment_term_id.exact_online_code:
            raise ValidationError(_('Please fill out the Exact Online code for Payment term %s before creating this partner') % res.property_supplier_payment_term_id.name)
        return res

    @api.multi
    def write(self, vals):
        if vals.get('property_payment_term_id'):
            payment_term = self.env['account.payment.term'].browse(vals.get('property_payment_term_id'))
            if not payment_term.exact_online_code:
                raise ValidationError(_('Please fill out the Exact Online code for Payment term %s before updating this partner') % payment_term.name)
        if vals.get('property_supplier_payment_term_id'):
            payment_term = self.env['account.payment.term'].browse(vals.get('property_supplier_payment_term_id'))
            if not payment_term.exact_online_code:
                raise ValidationError(_('Please fill out the Exact Online code for Payment term %s before updating this partner') % payment_term.name)
        return super(ResPartner, self).write(vals)