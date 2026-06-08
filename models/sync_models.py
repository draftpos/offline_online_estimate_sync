from odoo import api, fields, models

class SyncMixin(models.AbstractModel):
    _name = 'sync.mixin'
    _description = 'Sync Mixin'

    cloud_id = fields.Integer(string='Cloud ID', index=True, copy=False, readonly=True)
    
class Customer(models.Model):
    _inherit = ['customer', 'sync.mixin']
    _name = 'customer'

class VehicleMake(models.Model):
    _inherit = ['vehicle.make', 'sync.mixin']
    _name = 'vehicle.make'

class VehicleModel(models.Model):
    _inherit = ['vehicle.model', 'sync.mixin']
    _name = 'vehicle.model'

class Vehicle(models.Model):
    _inherit = ['vehicle', 'sync.mixin']
    _name = 'vehicle'

class ProductTemplate(models.Model):
    _inherit = ['product.template', 'sync.mixin']
    _name = 'product.template'

class ProductProduct(models.Model):
    _inherit = ['product.product', 'sync.mixin']
    _name = 'product.product'

class Estimate(models.Model):
    _inherit = ['estimate', 'sync.mixin']
    _name = 'estimate'

class EstimateLine(models.Model):
    _inherit = ['estimate.line', 'sync.mixin']
    _name = 'estimate.line'
