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

    create_date = fields.Datetime(readonly=True)
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
        res = super(AccountMove, self.with_context(syncing_exact=True)).create(vals)
        # Check if journal is OK for Exact syncing
        if res.journal_id and not res.journal_id.exact_online_no_sync and not res.journal_id.exact_online_code:
            raise ValidationError(_('Please fill out the Exact Online code for Journal %s before creating this') % res.journal_id.name)
        # If move was created as posted, sync immediately
        if res.state == 'posted' and not res.journal_id.exact_online_no_sync:
            res.exact_online_queue_create()
        return res

    @api.multi
    def exact_online_queue_create(self):
        for move in self:
            company = move.exact_get_company()
            # Only sync moves after the Exact Online 'block date'
            if not company.exact_online_sync_from or (company.exact_online_sync_from and company.exact_online_sync_from <= move.date):
                # Only sync moves for partners that don't sync their invoices and for journals for which we may sync
                if not move.journal_id.exact_online_no_sync and (not move.partner_id or not move.partner_id.exact_sync_invoices):
                    move.exact_online_state = 'to sync'
                    self.env['exact_online.job'].sudo().create({
                        'res_model': self._name,
                        'res_ids': move.id,
                        'method': 'create',
                        'company_id': company.id if company else False,
                    })

    @api.multi
    def post(self):
        super(AccountMove, self).post()
        self.exact_online_queue_create()


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
