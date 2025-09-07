# Import all views to make them accessible from core.views
# Add bill views to the imports
from .bill_views import BillListView, BillDetailView, BillGenerateView
from .base_views import *
from .students import *
from .parents import *
from .fees import *
from .grades import *
from .attendance import *
from .analytics import *
from .assignments import *
from .timetable import *
from .subjects import *
from .teachers import *
from .class_assignments import *
from .api import *
from .misc import *