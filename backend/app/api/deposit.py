"""
充值 & Token 余额 API
POST /api/deposit/create-order   - 创建充值订单
POST /api/deposit/submit-tx      - 提交 tx hash 验证
GET  /api/deposit/platform-address - 获取平台收款地址
GET  /api/deposit/order/<order_no> - 查询订单状态
GET  /api/deposit/balance          - 查询 Token 余额
GET  /api/deposit/history          - Token 流水列表
"""

from datetime import datetime
from decimal import Decimal

from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from . import deposit_bp
from ..config import Config
from ..extensions import db
from ..models.user import User
from ..models.deposit import DepositOrder, TokenTransaction
from ..services.polygon_service import PolygonService
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


@deposit_bp.route('/create-order', methods=['POST'])
@jwt_required()
def create_order():
    """创建充值订单"""
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}
    amount_usdt = data.get('amount_usdt')

    if not amount_usdt or float(amount_usdt) <= 0:
        return jsonify({"success": False, "error": "金额无效"}), 400

    amount = Decimal(str(amount_usdt))
    order = DepositOrder(
        user_id=user_id,
        order_no=DepositOrder.generate_order_no(),
        amount_usdt=amount,
        tokens_credit=amount,  # 1 USDT = 1 Token
        status='pending',
    )
    db.session.add(order)
    db.session.commit()

    return jsonify({"success": True, "order_no": order.order_no, "amount_usdt": float(amount)})


@deposit_bp.route('/submit-tx', methods=['POST'])
@jwt_required()
def submit_tx():
    """绑定 tx hash 并验证链上交易"""
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}
    order_no = data.get('order_no', '').strip()
    tx_hash = data.get('tx_hash', '').strip()

    if not order_no or not tx_hash:
        return jsonify({"success": False, "error": "参数缺失"}), 400

    # 校验 tx hash 格式
    if not tx_hash.startswith('0x') or len(tx_hash) != 66:
        return jsonify({"success": False, "error": "tx hash 格式无效"}), 400

    order = DepositOrder.query.filter_by(order_no=order_no, user_id=user_id).first()
    if not order:
        return jsonify({"success": False, "error": "订单不存在"}), 404

    if order.status not in ('pending', 'confirming'):
        return jsonify({"success": False, "error": f"订单状态不可提交: {order.status}"}), 400

    # 防重放: tx_hash 已被其他订单使用
    existing = DepositOrder.query.filter_by(tx_hash=tx_hash).first()
    if existing and existing.id != order.id:
        return jsonify({"success": False, "error": "该交易哈希已被使用"}), 400

    # 调用 Polygon 验证
    try:
        polygon = PolygonService()
        result = polygon.verify_usdt_transfer(tx_hash)
    except Exception as e:
        logger.error(f"Polygon 验证异常: {e}")
        return jsonify({"success": False, "error": f"验证服务异常: {e}"}), 500

    if result.get('success'):
        # 验证通过 → 写入 tx_hash 和结果
        actual_amount = Decimal(str(result['amount']))
        order.tx_hash = tx_hash
        order.from_address = result['from_address']
        order.confirmations = result['confirmations']
        order.amount_usdt = actual_amount
        order.tokens_credit = actual_amount  # 1:1
        order.status = 'completed'
        order.confirmed_at = datetime.utcnow()

        # 增加用户余额
        user = User.query.get(user_id)
        user.token_balance = (user.token_balance or Decimal(0)) + actual_amount

        # 记录流水
        tx_record = TokenTransaction(
            user_id=user_id,
            type='deposit',
            amount=actual_amount,
            balance=user.token_balance,
            reference=order.order_no,
        )
        db.session.add(tx_record)
        db.session.commit()

        logger.info(f"充值成功: user={user_id}, amount={actual_amount}, tx={tx_hash}")
        return jsonify({
            "success": True,
            "status": "completed",
            "amount": float(actual_amount),
            "balance": float(user.token_balance),
        })

    elif result.get('confirming'):
        # 确认数不足 → 记录进度，可重试
        order.tx_hash = tx_hash
        order.from_address = result.get('from_address')
        order.confirmations = result.get('confirmations', 0)
        order.status = 'confirming'
        db.session.commit()

        return jsonify({
            "success": False,
            "status": "confirming",
            "confirmations": result['confirmations'],
            "required": result['required'],
            "error": result['error'],
        })

    else:
        # 验证失败 → 不写入 tx_hash，订单保持 pending 可重试
        return jsonify({
            "success": False,
            "status": "failed",
            "error": result.get('error', '验证失败'),
        }), 400


@deposit_bp.route('/order/<order_no>', methods=['GET'])
@jwt_required()
def get_order(order_no):
    """查询订单状态"""
    user_id = int(get_jwt_identity())
    order = DepositOrder.query.filter_by(order_no=order_no, user_id=user_id).first()
    if not order:
        return jsonify({"success": False, "error": "订单不存在"}), 404

    return jsonify({"success": True, "order": order.to_dict()})


@deposit_bp.route('/balance', methods=['GET'])
@jwt_required()
def get_balance():
    """查询 Token 余额"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "error": "用户不存在"}), 404

    return jsonify({"success": True, "balance": float(user.token_balance or 0)})


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
