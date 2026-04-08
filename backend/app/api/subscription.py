"""
订阅 API
GET  /api/subscription/plans          — 公开，返回计划列表
GET  /api/subscription/current        — 需登录，返回当前订阅状态
POST /api/subscription/create-order   — 需登录，创建订阅订单
POST /api/subscription/verify-payment — 需登录，验证付款并激活订阅
"""

from datetime import datetime, timedelta
from decimal import Decimal

from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from . import subscription_bp
from ..config import Config
from ..extensions import db
from ..models.user import User
from ..models.subscription import Subscription, PLAN_CONFIG
from ..models.deposit import DepositOrder, TokenTransaction
from ..services.polygon_service import PolygonService
from ..utils.logger import get_logger

logger = get_logger('mirofish.api.subscription')


@subscription_bp.route('/plans', methods=['GET'])
def get_plans():
    """公开端点：返回所有订阅计划"""
    plans = []
    for key, cfg in PLAN_CONFIG.items():
        plans.append({
            "plan": key,
            "label": cfg['label'],
            "price": cfg['price'],
            "quota": cfg['quota'],
        })
    return jsonify({"success": True, "plans": plans})


@subscription_bp.route('/current', methods=['GET'])
@jwt_required()
def get_current():
    """获取当前用户的订阅状态 + 剩余额度"""
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"success": False, "error": "用户不存在"}), 404

    sub = user.get_active_subscription()
    remaining = user.get_remaining_quota()
    plan = sub.plan if sub else 'free'
    plan_label = PLAN_CONFIG.get(plan, {}).get('label', plan)

    return jsonify({
        "success": True,
        "plan": plan,
        "plan_label": plan_label,
        "subscription": sub.to_dict() if sub else None,
        "remaining_quota": remaining,
        "total_quota": sub.quota if sub else Config.FREE_MONTHLY_QUOTA,
    })


@subscription_bp.route('/create-order', methods=['POST'])
@jwt_required()
def create_order():
    """创建订阅订单"""
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}
    plan = data.get('plan', '').strip()

    if plan not in ('basic', 'pro', 'premium'):
        return jsonify({"success": False, "error": "无效的订阅计划"}), 400

    price = PLAN_CONFIG[plan]['price']
    amount = Decimal(str(price))

    order = DepositOrder(
        user_id=user_id,
        order_no=DepositOrder.generate_order_no(),
        amount_usdt=amount,
        tokens_credit=Decimal(0),  # subscription, not token credit
        plan=plan,
        status='pending',
    )
    db.session.add(order)
    db.session.commit()

    return jsonify({
        "success": True,
        "order_no": order.order_no,
        "plan": plan,
        "amount_usdt": float(amount),
    })


@subscription_bp.route('/verify-payment', methods=['POST'])
@jwt_required()
def verify_payment():
    """验证链上付款并激活订阅"""
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}
    order_no = data.get('order_no', '').strip()
    tx_hash = data.get('tx_hash', '').strip()

    if not order_no or not tx_hash:
        return jsonify({"success": False, "error": "参数缺失"}), 400

    if not tx_hash.startswith('0x') or len(tx_hash) != 66:
        return jsonify({"success": False, "error": "tx hash 格式无效"}), 400

    order = DepositOrder.query.filter_by(order_no=order_no, user_id=user_id).first()
    if not order:
        return jsonify({"success": False, "error": "订单不存在"}), 404

    if order.status not in ('pending', 'confirming'):
        return jsonify({"success": False, "error": f"订单状态不可提交: {order.status}"}), 400

    if not order.plan:
        return jsonify({"success": False, "error": "该订单非订阅订单"}), 400

    # 防重放
    existing = DepositOrder.query.filter_by(tx_hash=tx_hash).first()
    if existing and existing.id != order.id:
        return jsonify({"success": False, "error": "该交易哈希已被使用"}), 400

    # Polygon 验证
    try:
        polygon = PolygonService()
        result = polygon.verify_usdt_transfer(tx_hash)
    except Exception as e:
        logger.error(f"Polygon 验证异常: {e}")
        return jsonify({"success": False, "error": f"验证服务异常: {e}"}), 500

    if result.get('success'):
        actual_amount = Decimal(str(result['amount']))
        required_price = Decimal(str(PLAN_CONFIG[order.plan]['price']))

        # 金额不足 → 根据实际金额自动匹配可负担的最高计划
        if actual_amount < required_price:
            matched_plan = _match_plan_by_amount(actual_amount)
            if not matched_plan:
                return jsonify({
                    "success": False,
                    "error": f"转账金额 ${actual_amount} 不足以购买任何付费计划（最低 ${PLAN_CONFIG['basic']['price']}）",
                    "actual_amount": float(actual_amount),
                    "required": float(required_price),
                }), 400
            order.plan = matched_plan
            logger.info(f"金额不匹配，自动降级: {order.plan} → {matched_plan} (实际 ${actual_amount})")

        order.tx_hash = tx_hash
        order.from_address = result['from_address']
        order.confirmations = result['confirmations']
        order.amount_usdt = actual_amount
        order.status = 'completed'
        order.confirmed_at = datetime.utcnow()

        plan = order.plan
        plan_cfg = PLAN_CONFIG[plan]
        plan_price = Decimal(str(plan_cfg['price']))
        base_quota = plan_cfg['quota']

        # 超额部分按单次单价折算为额外次数
        bonus = 0
        if actual_amount > plan_price:
            per_cost = plan_price / base_quota
            bonus = int((actual_amount - plan_price) / per_cost)
        final_quota = base_quota + bonus

        if bonus:
            logger.info(f"超额充值: 实付${actual_amount}, 计划${plan_price}, 补充{bonus}次, 总额度{final_quota}")

        # 创建/更新订阅
        user = db.session.get(User, user_id)
        sub = user.subscription
        now = datetime.utcnow()

        if sub and sub.is_active:
            # 有活跃订阅：延长 30 天, used 重置, plan 更新
            sub.period_end = sub.period_end + timedelta(days=30)
            sub.used = 0
            sub.plan = plan
            sub.quota = final_quota
            sub.status = 'active'
            sub.updated_at = now
        elif sub:
            # 有过期订阅：重新激活
            sub.plan = plan
            sub.status = 'active'
            sub.period_start = now
            sub.period_end = now + timedelta(days=30)
            sub.quota = final_quota
            sub.used = 0
            sub.updated_at = now
        else:
            # 无订阅：新建
            sub = Subscription(
                user_id=user_id,
                plan=plan,
                status='active',
                period_start=now,
                period_end=now + timedelta(days=30),
                quota=final_quota,
                used=0,
            )
            db.session.add(sub)

        # 记录流水
        tx_record = TokenTransaction(
            user_id=user_id,
            type='subscribe',
            amount=-actual_amount,
            balance=user.token_balance or Decimal(0),
            reference=order.order_no,
        )
        db.session.add(tx_record)
        db.session.commit()

        logger.info(f"订阅激活: user={user_id}, plan={plan}, tx={tx_hash}")
        return jsonify({
            "success": True,
            "status": "completed",
            "plan": plan,
            "subscription": sub.to_dict(),
        })

    elif result.get('confirming'):
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
        return jsonify({
            "success": False,
            "status": "failed",
            "error": result.get('error', '验证失败'),
        }), 400


def _match_plan_by_amount(amount: Decimal) -> str | None:
    """根据实际转账金额匹配可负担的最高计划，返回 plan key 或 None"""
    # 按价格从高到低排，取能负担的最高档
    paid_plans = [(k, v) for k, v in PLAN_CONFIG.items() if v['price'] > 0]
    paid_plans.sort(key=lambda x: x[1]['price'], reverse=True)
    for plan_key, cfg in paid_plans:
        if amount >= Decimal(str(cfg['price'])):
            return plan_key
    return None


def _refund_quota(user_id: int, task_id: str, log=None):
    """退还订阅额度（预测失败时调用）"""
    user = db.session.get(User, user_id)
    if not user:
        return
    sub = user.get_active_subscription()
    if sub and sub.used > 0:
        sub.used -= 1
        db.session.commit()
        if log:
            log.info(f"预测失败，已退还 1 次额度给用户 {user_id} (task={task_id[:8]}...)")
    # 免费用户：失败的任务状态变 failed 后不计入 count（_count_free_predictions_this_month 只统计 completed/processing/pending）
