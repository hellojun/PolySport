"""
充值 & Token 流水 API（订阅制后保留的端点）
GET  /api/deposit/platform-address - 获取平台收款地址
GET  /api/deposit/balance          - 查询订阅状态 & 剩余额度
GET  /api/deposit/history          - Token 流水列表
"""

from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from . import deposit_bp
from ..config import Config
from ..extensions import db
from ..models.user import User
from ..models.deposit import TokenTransaction
from ..utils.logger import get_logger

logger = get_logger('mirofish.api.deposit')


@deposit_bp.route('/platform-address', methods=['GET'])
@jwt_required()
def get_platform_address():
    """返回平台收款地址信息"""
    return jsonify({
        "success": True,
        "address": Config.PLATFORM_WALLET_ADDRESS,
        "usdt_contract": Config.POLYGON_USDT_CONTRACT,
        "chain": "Polygon",
        "chain_id": 137,
    })


@deposit_bp.route('/balance', methods=['GET'])
@jwt_required()
def get_balance():
    """查询订阅状态 & 剩余额度"""
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"success": False, "error": "用户不存在"}), 404

    sub = user.get_active_subscription()
    return jsonify({
        "success": True,
        "balance": float(user.token_balance or 0),
        "remaining_quota": user.get_remaining_quota(),
        "subscription": sub.to_dict() if sub else None,
    })


@deposit_bp.route('/history', methods=['GET'])
@jwt_required()
def get_history():
    """Token 流水列表"""
    user_id = int(get_jwt_identity())
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    per_page = min(per_page, 50)

    query = TokenTransaction.query.filter_by(user_id=user_id).order_by(
        TokenTransaction.created_at.desc()
    )
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    items = [t.to_dict() for t in pagination.items]

    return jsonify({
        "success": True,
        "transactions": items,
        "total": pagination.total,
        "page": page,
        "pages": pagination.pages,
    })
