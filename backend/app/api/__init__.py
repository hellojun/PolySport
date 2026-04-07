"""
API路由模块
"""

from flask import Blueprint

prediction_bp = Blueprint('prediction', __name__)
auth_bp = Blueprint('auth', __name__)
deposit_bp = Blueprint('deposit', __name__)
nft_bp = Blueprint('nft', __name__)
subscription_bp = Blueprint('subscription', __name__)

from . import prediction  # noqa: E402, F401
from . import auth  # noqa: E402, F401
from . import deposit  # noqa: E402, F401
from . import nft  # noqa: E402, F401
from . import subscription  # noqa: E402, F401
