# -*- coding: utf-8 -*-

{
    'name': 'Exact Online Connector',
    'version': '1.0',
    'summary': 'Odoo - Exact Online Connector',
    'description': """

    """,
    'category': '',
    'author': 'Callista',
    'website': 'https://www.callista.be',
    'depends': [
        'base',
        'account',
    ],
    'data': [
        'data/cron_data.xml',
        'data/exact_account_data.xml',
        'data/exact_online_data.xml',
        'security/ir.model.access.csv',
        'views/account_view.xml',
        'views/exact_online_view.xml',
        'views/partner_view.xml',
        'views/res_company_view.xml',
    ],
    'demo': [

    ],
    'qweb': [

    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
