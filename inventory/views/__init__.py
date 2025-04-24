# This file imports and exposes all views from the module files
# to maintain compatibility with existing imports like `from . import views`

from .department_views import *
from .product_stock_views import *
# Import all views from the module files
from .stock_movement_views import *
from .stock_take_views import *
from .warehouse_views import *
