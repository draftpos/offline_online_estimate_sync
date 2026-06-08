from odoo import api, fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    cloud_sync_url = fields.Char(
        string='Cloud Server URL',
        config_parameter='offline_online_estimate_sync.cloud_sync_url',
        help='URL of the central cloud Odoo instance (e.g. http://80.241.213.153:8069)',
    )
    cloud_sync_db = fields.Char(
        string='Cloud Database',
        config_parameter='offline_online_estimate_sync.cloud_sync_db',
        help='Name of the database on the central cloud server',
    )
    cloud_sync_username = fields.Char(
        string='Cloud Username / API Key',
        config_parameter='offline_online_estimate_sync.cloud_sync_username',
        help='Username or API Key for the cloud server',
    )
    cloud_sync_password = fields.Char(
        string='Cloud Password',
        config_parameter='offline_online_estimate_sync.cloud_sync_password',
        help='Password for the cloud server. Store safely.',
    )
    cloud_last_sync_date = fields.Datetime(
        string='Last Sync Date',
        config_parameter='offline_online_estimate_sync.cloud_last_sync_date',
        readonly=True,
    )

    def action_test_connection(self):
        self.ensure_one()
        self.env['sync.engine'].test_connection()

    def action_generate_api_key(self):
        self.ensure_one()
        new_key = self.env['sync.engine'].generate_api_key()
        if new_key:
            self.cloud_sync_password = new_key
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'API Key Generated',
                    'message': 'A secure API Key has been generated and saved. Please save the settings.',
                    'sticky': False,
                }
            }

    def action_sync_now(self):
        self.ensure_one()
        self.env['sync.engine'].action_sync_now()
