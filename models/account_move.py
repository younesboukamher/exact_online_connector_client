# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def exact_fields_to_monitor(self):
        return [
            'currency_id',
            'date',
            'journal_id',
            'name',
            'partner_id',
            'ref',
        ]

    exact_online_initial_sync = fields.Boolean()
    exact_online_state = fields.Selection([
        ('synced', 'Synced'),
        ('to sync', 'To sync'),
        ('syncing', 'Syncing'),
        ('sync exception', 'Sync Exception'),
        ('no', 'Nothing to sync')
    ], default='no')

    @api.model
    def create(self, vals):
        partner = False
        res = False
        if 'partner_id' in vals:
            partner = self.env['res.partner'].browse(vals.get('partner_id'))
        elif 'line_ids' in vals and vals.get('line_ids') and len(vals['line_ids'][0]) == 3 and vals['line_ids'][0][0] == 0 and vals['line_ids'][0][2].get('partner_id'):
            partner = self.env['res.partner'].browse(vals['line_ids'][0][2]['partner_id'])
        if partner and partner.exact_sync_invoices:
            vals['exact_online_state'] = 'no'
            res = super(AccountMove, self.with_context(syncing_exact=True)).create(vals)
        if not res:
            res = super(AccountMove, self.with_context(exact_no_sync_move_lines=True)).create(vals)
        if res.journal_id and not res.journal_id.exact_online_code:
            raise ValidationError(_('Please fill out the Exact Online code for Journal %s before creating this') % res.journal_id.name)
        return res

    @api.multi
    def write(self, vals):
        res = super(AccountMove, self).write(vals)
        return res


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.model
    def exact_fields_to_monitor(self):
        return [
            'account_id',
            'balance',
            'date',
            'exact_online_cost_center',
            'journal_id',
            'move_id',
            'name',
            'narration',
            'product_id',
            'quantity',
            'tax_ids',
            'tax_line_id'
        ]

    @api.multi
    def create(self, vals):
        res = False
        if self._context.get('exact_no_sync_move_lines') and 'exact_online_state' not in vals:
            vals['exact_online_state'] = 'syncing'
        if 'move_id' in vals:
            move = self.env['account.move'].browse(vals.get('move_id'))
            if move.exact_online_initial_sync:
                res = super(AccountMoveLine, self).create(vals)
        if not res:
            vals['exact_online_state'] = 'syncing'
            res = super(AccountMoveLine, self.with_context(syncing_exact=True)).create(vals)
        return res

    exact_online_initial_sync = fields.Boolean()
    exact_online_state = fields.Selection([
        ('synced', 'Synced'),
        ('to sync', 'To sync'),
        ('syncing', 'Syncing'),
        ('sync exception', 'Sync Exception'),
        ('no', 'Nothing to sync')
    ], default='to sync')
