"""
认证 API 路由
POST /api/auth/send-code     - 发送验证码
POST /api/auth/verify-code   - 验证验证码
POST /api/auth/register      - 注册
POST /api/auth/login         - 登录
POST /api/auth/google        - Google 一键登录
POST /api/auth/refresh       - 刷新 access token
POST /api/auth/logout        - 登出
GET  /api/auth/me            - 获取当前用户信息
"""

import random
import string

from flask import request, jsonify
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
)

from decimal import Decimal

from . import auth_bp
from ..config import Config
from ..extensions import db
from ..models.user import User
from ..models.deposit import TokenTransaction
from ..services.email_service import send_verification_code
from ..utils.redis_client import get_redis
from ..utils.logger import get_logger

logger = get_logger('mirofish.api.auth')


def _generate_code(length=6):
    return ''.join(random.choices(string.digits, k=length))


@auth_bp.route('/send-code', methods=['POST'])
def send_code():
    """发送验证码到邮箱。purpose=register 时检查邮箱未注册，purpose=reset 时检查邮箱已注册。"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "请求体为空"}), 400

    email = (data.get('email') or '').strip().lower()
    if not email or '@' not in email:
        return jsonify({"success": False, "error": "无效的邮箱地址"}), 400

    purpose = data.get('purpose', '')  # 'register' | 'reset'

    # 注册时：检查邮箱是否已注册
    if purpose == 'register':
        if User.query.filter_by(email=email).first():
            return jsonify({"success": False, "error": "该邮箱已注册"}), 409

    # 重置密码时：检查邮箱是否存在
    if purpose == 'reset':
        if not User.query.filter_by(email=email).first():
            return jsonify({"success": False, "error": "该邮箱未注册"}), 404

    r = get_redis()

    # 限频：60s 内只能发送一次
    rate_key = f"email_rate:{email}"
    if r.get(rate_key):
        return jsonify({"success": False, "error": "发送过于频繁，请 60 秒后重试"}), 429

    # 生成验证码并存储
    code = _generate_code()
    code_key = f"email_code:{email}"
    attempts_key = f"email_attempts:{email}"
    r.set(code_key, code, ex=300)  # 5 分钟有效
    r.set(rate_key, "1", ex=60)    # 60 秒限频
    r.delete(attempts_key)          # 重置错误计数

    # 发送邮件
    try:
        send_verification_code(email, code)
    except Exception as e:
        logger.error(f"发送验证码失败: {e}")
        return jsonify({"success": False, "error": "发送验证码失败，请稍后重试"}), 500

    return jsonify({"success": True, "message": "验证码已发送"})


@auth_bp.route('/verify-code', methods=['POST'])
def verify_code():
    """验证验证码"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "请求体为空"}), 400

    email = (data.get('email') or '').strip().lower()
    code = (data.get('code') or '').strip()

    if not email or not code:
        return jsonify({"success": False, "error": "邮箱和验证码不能为空"}), 400

    r = get_redis()
    code_key = f"email_code:{email}"
    attempts_key = f"email_attempts:{email}"

    # 防暴力：5 次错误后拒绝
    attempts = int(r.get(attempts_key) or 0)
    if attempts >= 5:
        return jsonify({"success": False, "error": "验证码错误次数过多，请重新发送"}), 429

    stored_code = r.get(code_key)
    if not stored_code:
        return jsonify({"success": False, "error": "验证码已过期，请重新发送"}), 400

    if stored_code != code:
        r.incr(attempts_key)
        r.expire(attempts_key, 300)
        return jsonify({"success": False, "error": "验证码错误"}), 400

    # 验证成功：设置 verified 标记，清理验证码
    verified_key = f"email_verified:{email}"
    r.set(verified_key, "1", ex=600)  # 10 分钟有效
    r.delete(code_key)
    r.delete(attempts_key)

    return jsonify({"success": True, "message": "验证成功"})


@auth_bp.route('/register', methods=['POST'])
def register():
    """注册新用户"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "请求体为空"}), 400

    email = (data.get('email') or '').strip().lower()
    password = data.get('password', '')

    if not email or '@' not in email:
        return jsonify({"success": False, "error": "无效的邮箱地址"}), 400

    if len(password) < 6:
        return jsonify({"success": False, "error": "密码至少 6 位"}), 400

    # 检查邮箱是否已验证
    r = get_redis()
    verified_key = f"email_verified:{email}"
    if not r.get(verified_key):
        return jsonify({"success": False, "error": "请先完成邮箱验证"}), 400

    # 检查邮箱是否已注册
    if User.query.filter_by(email=email).first():
        return jsonify({"success": False, "error": "该邮箱已注册"}), 409

    # 创建用户，赠送注册奖励
    signup_bonus = Decimal('4')
    user = User(email=email, is_verified=True, token_balance=signup_bonus)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()  # 获取 user.id

    bonus_tx = TokenTransaction(
        user_id=user.id,
        type='signup_bonus',
        amount=signup_bonus,
        balance=signup_bonus,
        reference='signup',
    )
    db.session.add(bonus_tx)
    db.session.commit()

    # 清理验证标记
    r.delete(verified_key)

    # 签发 tokens
    access_token = create_access_token(
        identity=str(user.id),
        expires_delta=Config.JWT_ACCESS_TOKEN_EXPIRES,
    )
    refresh_token = create_refresh_token(
        identity=str(user.id),
        expires_delta=Config.JWT_REFRESH_TOKEN_EXPIRES,
    )

    logger.info(f"用户注册成功: {email}")
    return jsonify({
        "success": True,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user.to_dict(),
    })


@auth_bp.route('/login', methods=['POST'])
def login():
    """邮箱密码登录"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "请求体为空"}), 400

    email = (data.get('email') or '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({"success": False, "error": "邮箱和密码不能为空"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"success": False, "error": "邮箱或密码错误"}), 401

    access_token = create_access_token(
        identity=str(user.id),
        expires_delta=Config.JWT_ACCESS_TOKEN_EXPIRES,
    )
    refresh_token = create_refresh_token(
        identity=str(user.id),
        expires_delta=Config.JWT_REFRESH_TOKEN_EXPIRES,
    )

    return jsonify({
        "success": True,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user.to_dict(),
    })


@auth_bp.route('/google', methods=['POST'])
def google_login():
    """Google 一键登录 / 注册"""
    data = request.get_json()
    if not data or not data.get('credential'):
        return jsonify({"success": False, "error": "缺少 credential"}), 400

    client_id = Config.GOOGLE_CLIENT_ID
    if not client_id:
        return jsonify({"success": False, "error": "Google 登录未配置"}), 500

    # 验证 Google ID token
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests

        idinfo = google_id_token.verify_oauth2_token(
            data['credential'],
            google_requests.Request(),
            client_id,
        )
    except ValueError:
        return jsonify({"success": False, "error": "Invalid Google token"}), 401

    google_id = idinfo['sub']
    email = idinfo.get('email', '').lower()
    email_verified = idinfo.get('email_verified', False)

    if not email or not email_verified:
        return jsonify({"success": False, "error": "Google 账号邮箱未验证"}), 401

    # 查找或创建用户
    user = User.query.filter_by(google_id=google_id).first()

    if not user:
        # google_id 不存在，尝试用 email 匹配已有账号
        user = User.query.filter_by(email=email).first()
        if user:
            # 关联 google_id 到现有账号
            user.google_id = google_id
            db.session.commit()
        else:
            # 全新用户
            signup_bonus = Decimal('4')
            user = User(
                email=email,
                google_id=google_id,
                is_verified=True,
                token_balance=signup_bonus,
            )
            db.session.add(user)
            db.session.flush()

            bonus_tx = TokenTransaction(
                user_id=user.id,
                type='signup_bonus',
                amount=signup_bonus,
                balance=signup_bonus,
                reference='google_signup',
            )
            db.session.add(bonus_tx)
            db.session.commit()
            logger.info(f"Google 新用户注册: {email}")

    # 签发 JWT
    access_token = create_access_token(
        identity=str(user.id),
        expires_delta=Config.JWT_ACCESS_TOKEN_EXPIRES,
    )
    refresh_token = create_refresh_token(
        identity=str(user.id),
        expires_delta=Config.JWT_REFRESH_TOKEN_EXPIRES,
    )

    return jsonify({
        "success": True,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user.to_dict(),
    })


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """刷新 access token"""
    user_id = get_jwt_identity()
    access_token = create_access_token(
        identity=user_id,
        expires_delta=Config.JWT_ACCESS_TOKEN_EXPIRES,
    )
    return jsonify({
        "success": True,
        "access_token": access_token,
    })


@auth_bp.route('/logout', methods=['POST'])
@jwt_required(refresh=True)
def logout():
    """登出：将 refresh token 加入黑名单"""
    jti = get_jwt()["jti"]
    r = get_redis()
    # 黑名单有效期 = refresh token 有效期
    r.set(
        f"jwt_blacklist:{jti}", "1",
        ex=int(Config.JWT_REFRESH_TOKEN_EXPIRES.total_seconds()),
    )
    return jsonify({"success": True, "message": "已登出"})


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    """获取当前用户信息"""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user:
        return jsonify({"success": False, "error": "用户不存在"}), 404
    return jsonify({"success": True, "user": user.to_dict()})


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """重置密码（需先通过邮箱验证码验证）"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "请求体为空"}), 400

    email = (data.get('email') or '').strip().lower()
    password = data.get('password', '')

    if not email or '@' not in email:
        return jsonify({"success": False, "error": "无效的邮箱地址"}), 400

    if len(password) < 6:
        return jsonify({"success": False, "error": "密码至少 6 位"}), 400

    # 检查邮箱是否已验证
    r = get_redis()
    verified_key = f"email_verified:{email}"
    if not r.get(verified_key):
        return jsonify({"success": False, "error": "请先完成邮箱验证"}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"success": False, "error": "该邮箱未注册"}), 404

    user.set_password(password)
    db.session.commit()

    # 清理验证标记
    r.delete(verified_key)

    logger.info(f"用户重置密码成功: {email}")
    return jsonify({"success": True, "message": "密码重置成功"})
