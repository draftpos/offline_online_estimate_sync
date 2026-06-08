{
    'name': 'Offline Online Estimate Sync',
    'version': '1.0',
    'category': 'Customizations',
    'summary': 'Bi-directional synchronization engine for offline Odoo instances to a central cloud server',
    'author': 'Draft POS',
    'depends': ['base', 'job_card_management', 'sale', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'data/cron.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': True,
}
