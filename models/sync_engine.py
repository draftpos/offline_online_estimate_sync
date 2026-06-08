import xmlrpc.client
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

SYNC_MODELS = {
    'customer': {
        'fields': ['name', 'customer_type', 'email', 'phone', 'website', 'street', 'city', 'vat_number', 'registration_number', 'insurance_company_reg_no'],
        'm2o': {},
    },
    'vehicle.make': {
        'fields': ['name'],
        'm2o': {},
    },
    'vehicle.model': {
        'fields': ['name', 'make_id'],
        'm2o': {'make_id': 'vehicle.make'},
    },
    'vehicle': {
        'fields': ['name', 'make_id', 'model_id', 'chassis_number', 'reg_number', 'year_of_manufacture', 'color', 'customer_id'],
        'm2o': {'make_id': 'vehicle.make', 'model_id': 'vehicle.model', 'customer_id': 'customer'},
    },
    'product.template': {
        'fields': ['name', 'list_price', 'standard_price', 'type'],
        'm2o': {},
    },
    'product.product': {
        'fields': ['product_tmpl_id', 'default_code', 'active'],
        'm2o': {'product_tmpl_id': 'product.template'},
    },
    'estimate': {
        'fields': ['name', 'customer_id', 'vehicle_id', 'state', 'date_order', 'validity_date'],
        'm2o': {'customer_id': 'customer', 'vehicle_id': 'vehicle'},
    },
    'estimate.line': {
        'fields': ['estimate_id', 'product_id', 'name', 'product_uom_qty', 'price_unit'],
        'm2o': {'estimate_id': 'estimate', 'product_id': 'product.product'},
    }
}

class SyncEngine(models.AbstractModel):
    _name = 'sync.engine'
    _description = 'Offline Online Sync Engine'

    def _get_credentials(self):
        ICPSudo = self.env['ir.config_parameter'].sudo()
        url = ICPSudo.get_param('offline_online_estimate_sync.cloud_sync_url')
        db = ICPSudo.get_param('offline_online_estimate_sync.cloud_sync_db')
        username = ICPSudo.get_param('offline_online_estimate_sync.cloud_sync_username')
        password = ICPSudo.get_param('offline_online_estimate_sync.cloud_sync_password')
        return url, db, username, password

    def _connect(self, url, db, username, password):
        if not all([url, db, username, password]):
            raise UserError(_("Cloud Sync Configuration is missing. Please check Settings."))
        try:
            common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
            uid = common.authenticate(db, username, password, {})
            if not uid:
                raise UserError(_("Authentication failed. Please check credentials."))
            models_api = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
            return uid, models_api
        except Exception as e:
            _logger.error(f"Sync Connection Error: {e}")
            raise UserError(_("Failed to connect to cloud server: %s" % str(e)))

    def generate_api_key(self):
        url, db, username, password = self._get_credentials()
        uid, models_api = self._connect(url, db, username, password)
        try:
            # Check if key exists
            existing_keys = models_api.execute_kw(db, uid, password, 'res.users.apikeys', 'search_read', [[('user_id', '=', uid), ('name', '=', 'Offline Sync Key')]], {'fields': ['id']})
            if existing_keys:
                models_api.execute_kw(db, uid, password, 'res.users.apikeys', 'unlink', [[k['id'] for k in existing_keys]])
            # Create new key
            new_key = models_api.execute_kw(db, uid, password, 'res.users.apikeys', '_generate', ['Offline Sync Key', uid])
            return new_key
        except Exception as e:
            raise UserError(_("Failed to generate API Key: %s" % str(e)))

    def test_connection(self):
        url, db, username, password = self._get_credentials()
        uid, models_api = self._connect(url, db, username, password)
        company = models_api.execute_kw(db, uid, password, 'res.company', 'search_read', [[]], {'fields': ['name'], 'limit': 1})
        if company:
            raise UserError(_("Connection Successful! Connected to cloud company: %s" % company[0].get('name')))
        else:
            raise UserError(_("Connection Successful, but no company found."))

    def action_sync_now(self):
        self._run_sync()

    def _run_sync(self):
        _logger.info("Starting Offline Online Sync Process...")
        url, db, username, password = self._get_credentials()
        try:
            uid, models_api = self._connect(url, db, username, password)
        except Exception as e:
            _logger.warning("Auto sync failed to connect: %s", str(e))
            return
        
        ICPSudo = self.env['ir.config_parameter'].sudo()
        last_sync = ICPSudo.get_param('offline_online_estimate_sync.cloud_last_sync_date')
        
        pull_domain = []
        if last_sync:
            pull_domain = [('write_date', '>', last_sync)]

        # --- PULL LOGIC ---
        self._sync_pull_users(db, uid, password, models_api, pull_domain)
        for model in SYNC_MODELS.keys():
            self._sync_pull_records(model, db, uid, password, models_api, pull_domain)

        # --- PUSH LOGIC ---
        for model in SYNC_MODELS.keys():
            self._sync_push_records(model, db, uid, password, models_api, last_sync)

        ICPSudo.set_param('offline_online_estimate_sync.cloud_last_sync_date', fields.Datetime.now())
        _logger.info("Offline Online Sync Process Completed Successfully.")

    def _sync_pull_users(self, db, uid, password, models_api, domain):
        try:
            cloud_users = models_api.execute_kw(db, uid, password, 'res.users', 'search_read', [domain], {'fields': ['name', 'login', 'password']})
            for c_user in cloud_users:
                local_user = self.env['res.users'].search([('login', '=', c_user['login'])], limit=1)
                vals = {'name': c_user['name']}
                if c_user.get('password'):
                    vals['password'] = c_user['password']
                if local_user:
                    local_user.with_context(skip_sync=True).write(vals)
                else:
                    vals['login'] = c_user['login']
                    self.env['res.users'].with_context(skip_sync=True).create(vals)
        except Exception as e:
            _logger.error("Error pulling users: %s", e)

    def _map_m2o_from_cloud_to_local(self, model_name, field_name, cloud_rec_id):
        if not cloud_rec_id:
            return False
        # cloud_rec_id is usually [id, 'name'] in XMLRPC
        c_id = cloud_rec_id[0] if isinstance(cloud_rec_id, (list, tuple)) else cloud_rec_id
        target_model = SYNC_MODELS[model_name]['m2o'][field_name]
        local_rec = self.env[target_model].search([('cloud_id', '=', c_id)], limit=1)
        return local_rec.id if local_rec else False

    def _map_m2o_from_local_to_cloud(self, model_name, field_name, local_rec_id):
        if not local_rec_id:
            return False
        target_model = SYNC_MODELS[model_name]['m2o'][field_name]
        local_rec = self.env[target_model].browse(local_rec_id)
        return local_rec.cloud_id if local_rec.cloud_id else False

    def _sync_pull_records(self, model_name, db, uid, password, models_api, domain):
        try:
            fields_to_read = SYNC_MODELS[model_name]['fields'] + ['id', 'write_date']
            cloud_recs = models_api.execute_kw(db, uid, password, model_name, 'search_read', [domain], {'fields': fields_to_read})
            
            for cr in cloud_recs:
                local_rec = self.env[model_name].search([('cloud_id', '=', cr['id'])], limit=1)
                vals = {'cloud_id': cr['id']}
                for f in SYNC_MODELS[model_name]['fields']:
                    if f in SYNC_MODELS[model_name]['m2o']:
                        vals[f] = self._map_m2o_from_cloud_to_local(model_name, f, cr.get(f))
                    else:
                        vals[f] = cr.get(f)
                
                if local_rec:
                    # Very basic conflict resolution: Cloud wins for pull (you can tweak this)
                    local_rec.with_context(skip_sync=True).write(vals)
                else:
                    self.env[model_name].with_context(skip_sync=True).create(vals)
        except Exception as e:
            _logger.error("Error pulling %s: %s", model_name, e)

    def _sync_push_records(self, model_name, db, uid, password, models_api, last_sync):
        try:
            domain = [('write_date', '>', last_sync)] if last_sync else []
            local_recs = self.env[model_name].search(domain)
            for lr in local_recs:
                if self.env.context.get('skip_sync'):
                    continue
                vals = {}
                for f in SYNC_MODELS[model_name]['fields']:
                    if f in SYNC_MODELS[model_name]['m2o']:
                        # map local many2one ID to cloud ID
                        local_val = getattr(lr, f).id
                        vals[f] = self._map_m2o_from_local_to_cloud(model_name, f, local_val)
                    else:
                        vals[f] = getattr(lr, f)
                
                if lr.cloud_id:
                    # Write to cloud
                    models_api.execute_kw(db, uid, password, model_name, 'write', [[lr.cloud_id], vals])
                else:
                    # Create on cloud
                    new_c_id = models_api.execute_kw(db, uid, password, model_name, 'create', [vals])
                    if new_c_id:
                        lr.with_context(skip_sync=True).write({'cloud_id': new_c_id})
        except Exception as e:
            _logger.error("Error pushing %s: %s", model_name, e)
