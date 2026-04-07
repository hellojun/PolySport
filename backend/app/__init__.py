"""
MiroFish Backend - Flask应用工厂
"""

import os
import warnings

warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request
from flask_cors import CORS

from .config import Config
from .extensions import db, jwt
from .utils.logger import setup_logger, get_logger


def _ensure_system_user(app, logger):
    """确保系统用户存在（自动预测使用）"""
    try:
        with app.app_context():
            from .extensions import db
            from .models.user import User
            from .config import Config as C

            email = C.SYSTEM_USER_EMAIL
            user = User.query.filter_by(email=email).first()
            if not user:
                user = User(email=email, is_verified=True)
                db.session.add(user)
                db.session.commit()
                logger.info(f"已创建系统用户: {email}")
            else:
                logger.info(f"系统用户已存在: {email}")
    except Exception as e:
        logger.warning(f"创建系统用户失败: {e}")


def _cleanup_interrupted_tasks(app, logger):
    """启动时将被中断的 pending/processing 任务标记为 failed 并退还订阅额度"""
    from datetime import datetime
    try:
        with app.app_context():
            from .extensions import db
            from .models.prediction_task import PredictionTask
            from .models.user import User
            from .config import Config as C

            interrupted = PredictionTask.query.filter(
                PredictionTask.status.in_(['pending', 'processing'])
            ).all()

            if not interrupted:
                return

            logger.info(f"发现 {len(interrupted)} 个被中断的预测任务，正在清理...")

            system_email = C.SYSTEM_USER_EMAIL
            system_user = User.query.filter_by(email=system_email).first()
            system_user_id = system_user.id if system_user else None

            for task in interrupted:
                task.status = 'failed'
                task.error = '服务重启，任务被中断'
                task.updated_at = datetime.utcnow()

                # 退还订阅额度（跳过系统用户）
                user_id = task.user_id or (task.metadata_ or {}).get('user_id')
                if user_id and user_id != system_user_id:
                    user = db.session.get(User, user_id)
                    if user:
                        sub = user.get_active_subscription()
                        if sub and sub.used > 0:
                            sub.used -= 1
                            logger.info(f"  任务 {task.id[:8]}... 退还 1 次额度给用户 {user_id}")

            db.session.commit()
            logger.info(f"清理完成，共处理 {len(interrupted)} 个任务")
    except Exception as e:
        logger.warning(f"清理中断任务失败: {e}")


def create_app(config_class=Config):
    """Flask应用工厂函数"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False

    logger = setup_logger('mirofish')

    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process

    if should_log_startup:
        logger.info("=" * 50)
        logger.info("MiroFish Backend 启动中...")
        logger.info("=" * 50)

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # 初始化 Flask 扩展
    db.init_app(app)
    jwt.init_app(app)

    # JWT 黑名单回调：检查 Redis 中的 jwt_blacklist:<jti>
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        from .utils.redis_client import get_redis
        jti = jwt_payload["jti"]
        r = get_redis()
        if r is None:
            return False
        return r.get(f"jwt_blacklist:{jti}") is not None

    @app.before_request
    def log_request():
        logger = get_logger('mirofish.request')
        logger.debug(f"请求: {request.method} {request.path}")
        if request.content_type and 'json' in request.content_type:
            logger.debug(f"请求体: {request.get_json(silent=True)}")

    @app.after_request
    def log_response(response):
        logger = get_logger('mirofish.request')
        logger.debug(f"响应: {response.status_code}")
        return response

    # 注册蓝图
    from .api import prediction_bp, auth_bp, deposit_bp, nft_bp, subscription_bp
    app.register_blueprint(prediction_bp, url_prefix='/api/prediction')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(deposit_bp, url_prefix='/api/deposit')
    app.register_blueprint(nft_bp, url_prefix='/api/nft')
    app.register_blueprint(subscription_bp, url_prefix='/api/subscription')

    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'MiroFish Backend'}

    # 创建数据库表
    with app.app_context():
        from .models.user import User  # noqa: F401
        from .models.deposit import DepositOrder, TokenTransaction  # noqa: F401
        from .models.prediction_task import PredictionTask  # noqa: F401
        from .models.prediction import Prediction  # noqa: F401
        from .models.subscription import Subscription  # noqa: F401
        db.create_all()

    # 确保系统用户存在（自动预测使用）
    if should_log_startup:
        _ensure_system_user(app, logger)

    # 启动时清理被中断的预测任务：标记 failed + 退还订阅额度
    if should_log_startup:
        _cleanup_interrupted_tasks(app, logger)

    # 聪明钱排行榜：启动检查 + 月度定时任务
    if should_log_startup:
        from .services.data_fetcher.smart_money import (
            check_and_refresh_on_startup,
            start_monthly_scheduler,
        )
        check_and_refresh_on_startup()
        start_monthly_scheduler()

    # 自动预测调度器
    if should_log_startup and Config.AUTO_PREDICT_ENABLED:
        from .services.auto_scheduler import AutoPredictionScheduler
        scheduler = AutoPredictionScheduler(app)
        scheduler.start()
        app.auto_scheduler = scheduler

    if should_log_startup:
        logger.info("MiroFish Backend 启动完成")

    from .cli import register_cli
    register_cli(app)

    return app
