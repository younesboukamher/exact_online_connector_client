# -*- coding: utf-8 -*-

from odoo import fields, models, api, _

# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountAccount(models.Model):
    _inherit = "account.account"

    @api.multi
    def exact_create(self):
        self.ensure_one()
        company = self.exact_get_company()
        success, message = company.call_exact({
            'model': self._name,
            'action': 'create',
            'data': {
                'res_id': self.code
            }
        })
        return success, message


class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def exact_get_search_field(self):
        return 'exact_online_vat_code'

    exact_online_vat_code = fields.Char()


class AccountPaymentTerm(models.Model):
    _inherit = "account.payment.term"

    @api.model
    def exact_get_search_field(self):
        return 'exact_online_code'

    exact_online_code = fields.Char()


class AccountJournal(models.Model):
    _inherit = "account.journal"

    @api.model
    def exact_get_search_field(self):
        return 'exact_online_code'

    exact_online_code = fields.Char()
